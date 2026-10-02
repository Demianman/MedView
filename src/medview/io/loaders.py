from __future__ import annotations

import tempfile
from collections.abc import Sequence
from pathlib import Path

import nibabel as nib
import numpy as np
import pydicom

from medview.models import MedViewError, Volume, VolumeMetadata, safe_filename

MAX_UPLOAD_BYTES = 256 * 1024 * 1024


def load_nifti(path: Path) -> Volume:
    try:
        image = nib.load(str(path))
        data = np.asarray(image.dataobj, dtype=np.float32)  # type: ignore[attr-defined]
    except Exception as exc:
        raise MedViewError(f"Invalid NIfTI file: {exc}") from exc
    if data.ndim != 3:
        raise MedViewError(f"Expected a 3D NIfTI volume, received {data.ndim}D")
    zooms = tuple(float(x) for x in image.header.get_zooms()[:3])  # type: ignore[attr-defined]
    warnings = () if all(x > 0 for x in zooms) else ("Invalid spacing replaced with 1 mm",)
    spacing = (
        zooms[0] if zooms[0] > 0 else 1.0,
        zooms[1] if zooms[1] > 0 else 1.0,
        zooms[2] if zooms[2] > 0 else 1.0,
    )
    meta = VolumeMetadata("NIfTI", safe_filename(path.name), data.shape, spacing, warnings=warnings)
    affine = np.asarray(image.affine, dtype=np.float64)  # type: ignore[attr-defined]
    return Volume(data, affine, meta)


def load_dicom_series(paths: Sequence[Path]) -> Volume:
    if not paths:
        raise MedViewError("No DICOM files were provided")
    datasets = []
    for path in paths:
        try:
            ds = pydicom.dcmread(str(path))
            if not hasattr(ds, "PixelData"):
                raise ValueError("missing PixelData")
            datasets.append(ds)
        except Exception as exc:
            raise MedViewError(f"Invalid DICOM file {safe_filename(path.name)}: {exc}") from exc
    series = {str(getattr(ds, "SeriesInstanceUID", "missing")) for ds in datasets}
    if len(series) != 1:
        raise MedViewError("DICOM files must belong to one series")
    shapes = {(int(ds.Rows), int(ds.Columns)) for ds in datasets}
    if len(shapes) != 1:
        raise MedViewError("DICOM slices have inconsistent dimensions")
    datasets.sort(
        key=lambda ds: float(getattr(ds, "SliceLocation", getattr(ds, "InstanceNumber", 0)))
    )
    slices = []
    for ds in datasets:
        arr = ds.pixel_array.astype(np.float32)
        arr = arr * float(getattr(ds, "RescaleSlope", 1.0)) + float(
            getattr(ds, "RescaleIntercept", 0.0)
        )
        slices.append(arr)
    data = np.stack(slices, axis=2)
    pixel_spacing = [float(x) for x in getattr(datasets[0], "PixelSpacing", [1.0, 1.0])]
    slice_spacing = float(
        getattr(datasets[0], "SpacingBetweenSlices", getattr(datasets[0], "SliceThickness", 1.0))
    )
    spacing = (pixel_spacing[0], pixel_spacing[1], abs(slice_spacing))
    affine = np.diag([*spacing, 1.0]).astype(np.float64)
    first = datasets[0]
    meta = VolumeMetadata(
        "DICOM",
        f"{len(paths)} slice series",
        data.shape,
        spacing,
        str(getattr(first, "Modality", "OT")),
        str(getattr(first, "PatientID", "ANON")),
        str(getattr(first, "StudyDescription", "")),
    )
    return Volume(data, affine, meta)


def load_uploaded_nifti(filename: str, content: bytes) -> Volume:
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise MedViewError("Upload is empty or exceeds the 256 MB safety limit")
    suffix = ".nii.gz" if filename.lower().endswith(".nii.gz") else ".nii"
    if not filename.lower().endswith((".nii", ".nii.gz")):
        raise MedViewError("Only .nii and .nii.gz files are accepted by this endpoint")
    with tempfile.TemporaryDirectory(prefix="medview-") as directory:
        path = Path(directory) / f"upload{suffix}"
        path.write_bytes(content)
        volume = load_nifti(path)
        volume.metadata = VolumeMetadata(
            **{**volume.metadata.__dict__, "source_name": safe_filename(filename)}
        )
        return volume
