from __future__ import annotations

import io
import logging
import tempfile
import zipfile
from pathlib import Path
from threading import RLock

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from medview.demo import generate_synthetic_volume
from medview.inference import DeterministicThresholdSegmenter
from medview.io import export_mask, load_dicom_series, load_nifti, load_uploaded_nifti
from medview.models import MedViewError, ViewPlane, Volume
from medview.processing import MaskHistory, mask_metrics, native_available
from medview.ui.rendering import paint_mask, render_png

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("medview")
ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"


class Store:
    def __init__(self) -> None:
        self.volume: Volume | None = None
        self.history = MaskHistory()
        self.provenance: dict[str, object] = {"type": "manual-only", "clinical_model": False}
        self.lock = RLock()

    def require(self) -> Volume:
        if self.volume is None:
            raise HTTPException(409, "No volume loaded")
        return self.volume


store = Store()
app = FastAPI(title="MedView", version="0.1.0")


class PaintRequest(BaseModel):
    plane: ViewPlane
    index: int = Field(ge=0)
    u: float = Field(ge=0, le=1)
    v: float = Field(ge=0, le=1)
    radius: int = Field(default=4, ge=1, le=30)
    value: int = Field(default=1, ge=0, le=1)


def status_payload(volume: Volume) -> dict[str, object]:
    metrics = mask_metrics(volume.mask, volume.metadata.spacing_mm)
    return {
        "loaded": True,
        "metadata": volume.metadata.as_dict(),
        "ranges": {
            "sagittal": volume.voxels.shape[0],
            "coronal": volume.voxels.shape[1],
            "axial": volume.voxels.shape[2],
        },
        "intensity": {"min": float(volume.voxels.min()), "max": float(volume.voxels.max())},
        "mask": {
            "voxel_count": metrics.voxel_count,
            "volume_mm3": round(metrics.volume_mm3, 2),
            "bounds": metrics.bounds,
            "backend": metrics.backend,
        },
        "native_core": native_available(),
        "history": {"can_undo": store.history.can_undo, "can_redo": store.history.can_redo},
    }


@app.exception_handler(MedViewError)
async def medview_error_handler(_request: object, exc: MedViewError) -> JSONResponse:
    logger.warning("input_error detail=%s", exc)
    return JSONResponse(status_code=422, content={"detail": str(exc), "state": "invalid-file"})


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB / "index.html")


@app.get("/static/{filename}")
def static(filename: str) -> FileResponse:
    if filename not in {"app.js", "styles.css"}:
        raise HTTPException(404)
    return FileResponse(WEB / filename)


@app.get("/api/status")
def status() -> dict[str, object]:
    if store.volume is None:
        return {"loaded": False, "state": "empty", "native_core": native_available()}
    with store.lock:
        return status_payload(store.volume)


@app.post("/api/load-demo")
def load_demo() -> dict[str, object]:
    path = ROOT / "demo_data" / "synthetic_abdomen.nii.gz"
    if not path.exists():
        generate_synthetic_volume(path)
    with store.lock:
        store.volume = load_nifti(path)
        store.history.reset()
        store.provenance = {"type": "manual-only", "clinical_model": False}
        logger.info("volume_loaded source=synthetic shape=%s", store.volume.voxels.shape)
        return status_payload(store.volume)


@app.post("/api/load-nifti")
async def load_nifti_upload(file: UploadFile = File(...)) -> dict[str, object]:
    content = await file.read(256 * 1024 * 1024 + 1)
    with store.lock:
        store.volume = load_uploaded_nifti(file.filename or "upload.nii", content)
        store.history.reset()
        store.provenance = {"type": "manual-only", "clinical_model": False}
        logger.info("volume_loaded source=nifti name=%s", store.volume.metadata.source_name)
        return status_payload(store.volume)


@app.post("/api/load-dicom")
async def load_dicom_upload(files: list[UploadFile] = File(...)) -> dict[str, object]:
    if not 1 <= len(files) <= 2000:
        raise MedViewError("Select between 1 and 2000 DICOM slices")
    with tempfile.TemporaryDirectory(prefix="medview-dicom-") as directory:
        paths = []
        total = 0
        for number, file in enumerate(files):
            content = await file.read(64 * 1024 * 1024 + 1)
            total += len(content)
            if total > 256 * 1024 * 1024:
                raise MedViewError("DICOM series exceeds the 256 MB safety limit")
            path = Path(directory) / f"slice-{number:05d}.dcm"
            path.write_bytes(content)
            paths.append(path)
        with store.lock:
            store.volume = load_dicom_series(paths)
            store.history.reset()
            store.provenance = {"type": "manual-only", "clinical_model": False}
            logger.info("volume_loaded source=dicom slices=%d", len(paths))
            return status_payload(store.volume)


@app.get("/api/slice/{plane}/{index}")
def slice_image(
    plane: ViewPlane, index: int, level: float = 40, width: float = 400, overlay: bool = True
) -> Response:
    with store.lock:
        volume = store.require()
        try:
            content = render_png(volume, plane, index, level, width, overlay)
        except IndexError as exc:
            raise HTTPException(422, str(exc)) from exc
    return Response(content, media_type="image/png", headers={"Cache-Control": "no-store"})


@app.post("/api/infer")
def infer() -> dict[str, object]:
    with store.lock:
        volume = store.require()
        provider = DeterministicThresholdSegmenter()
        store.history.checkpoint(volume.mask, "inference", provider=provider.name)
        volume.mask = provider.predict(volume.voxels)
        store.provenance = {
            "provider": provider.name,
            "type": "deterministic percentile threshold",
            "clinical_model": False,
        }
        logger.info("segmentation_completed provider=%s", provider.name)
        return {**status_payload(volume), "provider": provider.name, "clinical_model": False}


@app.post("/api/paint")
def paint(request: PaintRequest) -> dict[str, object]:
    with store.lock:
        volume = store.require()
        store.history.checkpoint(
            volume.mask,
            "manual_edit",
            plane=request.plane.value,
            slice_index=request.index,
            radius=request.radius,
            value=request.value,
        )
        try:
            paint_mask(
                volume,
                request.plane,
                request.index,
                request.u,
                request.v,
                request.radius,
                request.value,
            )
        except IndexError as exc:
            raise HTTPException(422, str(exc)) from exc
        return status_payload(volume)["mask"]  # type: ignore[return-value]


@app.post("/api/clear-mask")
def clear_mask() -> dict[str, object]:
    with store.lock:
        volume = store.require()
        store.history.checkpoint(volume.mask, "clear_mask")
        volume.mask.fill(0)
        return status_payload(volume)


@app.post("/api/undo")
def undo() -> dict[str, object]:
    with store.lock:
        volume = store.require()
        restored = store.history.undo(volume.mask)
        if restored is None:
            raise HTTPException(409, "Nothing to undo")
        volume.mask = restored
        return status_payload(volume)


@app.post("/api/redo")
def redo() -> dict[str, object]:
    with store.lock:
        volume = store.require()
        restored = store.history.redo(volume.mask)
        if restored is None:
            raise HTTPException(409, "Nothing to redo")
        volume.mask = restored
        return status_payload(volume)


@app.get("/api/export")
def export() -> StreamingResponse:
    with store.lock:
        volume = store.require()
        with tempfile.TemporaryDirectory(prefix="medview-export-") as directory:
            store.history.record("export", format="nifti+json")
            mask_path, metadata_path = export_mask(
                volume,
                Path(directory),
                audit_events=store.history.events(),
                provenance=store.provenance,
            )
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
                bundle.write(mask_path, mask_path.name)
                bundle.write(metadata_path, metadata_path.name)
            archive.seek(0)
            logger.info("mask_exported voxels=%d", int(volume.mask.sum()))
            return StreamingResponse(
                archive,
                media_type="application/zip",
                headers={"Content-Disposition": 'attachment; filename="medview_export.zip"'},
            )
