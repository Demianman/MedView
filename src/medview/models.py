from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray


class ViewPlane(StrEnum):
    AXIAL = "axial"
    SAGITTAL = "sagittal"
    CORONAL = "coronal"


@dataclass(frozen=True)
class VolumeMetadata:
    source_type: str
    source_name: str
    shape: tuple[int, int, int]
    spacing_mm: tuple[float, float, float]
    modality: str = "OT"
    patient_id: str = "ANON"
    study_description: str = "Synthetic / educational"
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "source_name": self.source_name,
            "shape": self.shape,
            "spacing_mm": self.spacing_mm,
            "modality": self.modality,
            "patient_id": self.patient_id,
            "study_description": self.study_description,
            "warnings": self.warnings,
        }


@dataclass
class Volume:
    voxels: NDArray[np.float32]
    affine: NDArray[np.float64]
    metadata: VolumeMetadata
    mask: NDArray[np.uint8] = field(init=False)

    def __post_init__(self) -> None:
        if self.voxels.ndim != 3 or min(self.voxels.shape) < 2:
            raise ValueError("A 3D volume with at least 2 voxels per axis is required")
        if not np.isfinite(self.voxels).all():
            raise ValueError("Volume contains non-finite values")
        if self.affine.shape != (4, 4):
            raise ValueError("Affine must be 4x4")
        self.mask = np.zeros(self.voxels.shape, dtype=np.uint8)


class MedViewError(RuntimeError):
    """Expected, user-displayable application error."""


def safe_filename(name: str) -> str:
    return Path(name).name.replace("\x00", "")
