from __future__ import annotations

import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import nibabel as nib
import numpy as np
import pydicom

from medview.models import MedViewError, Volume, VolumeMetadata, safe_filename

MAX_UPLOAD_BYTES = 256 * 1024 * 1024


def _dicom_geometry(
    datasets: Sequence[Any],
) -> tuple[list[Any], tuple[float, float, float], np.ndarray, tuple[str, ...]]:
    """Return patient-coordinate ordering, spacing, and affine for classic single-frame slices."""
    first = datasets[0]
    orientation = getattr(first, "ImageOrientationPatient", None)
    positions = [getattr(ds, "ImagePositionPatient", None) for ds in datasets]
    pixel_spacing = tuple(float(x) for x in getattr(first, "PixelSpacing", [1.0, 1.0]))
    if orientation is None or any(position is None for position in positions):
        ordered = sorted(
            datasets,
            key=lambda ds: float(getattr(ds, "SliceLocation", getattr(ds, "InstanceNumber", 0))),
        )
        slice_spacing = abs(
            float(getattr(first, "SpacingBetweenSlices", getattr(first, "SliceThickness", 1.0)))
        )
        spacing = (pixel_spacing[0], pixel_spacing[1], slice_spacing)
        return (
            ordered,
            spacing,
            np.diag([*spacing, 1.0]),
            ("Patient-coordinate tags missing; used spacing-only affine",),
        )

    direction = np.asarray(orientation, dtype=np.float64)
    if direction.shape != (6,):
        raise MedViewError("ImageOrientationPatient must contain six values")
    row_cosine, column_cosine = direction[:3], direction[3:]
    if not np.isclose(np.linalg.norm(row_cosine), 1.0, atol=1e-3) or not np.isclose(
        np.linalg.norm(column_cosine), 1.0, atol=1e-3
    ):
        raise MedViewError("DICOM orientation vectors are not unit length")
    normal = np.cross(row_cosine, column_cosine)
    if np.linalg.norm(normal) < 0.99:
        raise MedViewError("DICOM orientation vectors are not orthogonal")
    for ds in datasets[1:]:
        candidate = np.asarray(
            getattr(ds, "ImageOrientationPatient", orientation), dtype=np.float64
        )
        if not np.allclose(candidate, direction, atol=1e-4):
            raise MedViewError("DICOM slices have inconsistent orientation")
    projections = [
        float(np.dot(np.asarray(position, dtype=np.float64), normal)) for position in positions
    ]
    order = np.argsort(projections)
    ordered = [datasets[int(i)] for i in order]
    sorted_projections = np.asarray(projections)[order]
    if len(ordered) > 1:
        differences = np.diff(sorted_projections)
        slice_spacing = float(np.median(np.abs(differences)))
        if slice_spacing <= 0 or not np.allclose(
            np.abs(differences), slice_spacing, rtol=0.05, atol=1e-3
        ):
            raise MedViewError("DICOM slice positions are duplicated or irregular")
    else:
        slice_spacing = abs(float(getattr(first, "SliceThickness", 1.0)))
    spacing = (pixel_spacing[0], pixel_spacing[1], slice_spacing)
    origin = np.asarray(ordered[0].ImagePositionPatient, dtype=np.float64)
    affine = np.eye(4, dtype=np.float64)
    affine[:3, 0] = column_cosine * pixel_spacing[0]
    affine[:3, 1] = row_cosine * pixel_spacing[1]
    affine[:3, 2] = normal * slice_spacing
    affine[:3, 3] = origin
    return ordered, spacing, affine, ()


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
    datasets: list[Any] = []
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
    datasets, spacing, affine, geometry_warnings = _dicom_geometry(datasets)
    slices = []
    for ds in datasets:
        arr = ds.pixel_array.astype(np.float32)
        arr = arr * float(getattr(ds, "RescaleSlope", 1.0)) + float(
            getattr(ds, "RescaleIntercept", 0.0)
        )
        slices.append(arr)
    data = np.stack(slices, axis=2)
    first = datasets[0]
    meta = VolumeMetadata(
        "DICOM",
        f"{len(paths)} slice series",
        data.shape,
        spacing,
        str(getattr(first, "Modality", "OT")),
        str(getattr(first, "PatientID", "ANON")),
        str(getattr(first, "StudyDescription", "")),
        geometry_warnings,
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
