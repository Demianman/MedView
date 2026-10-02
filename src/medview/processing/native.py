from __future__ import annotations

import ctypes
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.ctypeslib import ndpointer
from numpy.typing import NDArray


@dataclass(frozen=True)
class MaskMetrics:
    voxel_count: int
    volume_mm3: float
    bounds: tuple[tuple[int, int], tuple[int, int], tuple[int, int]] | None
    backend: str


class _CMetrics(ctypes.Structure):
    _fields_ = [
        ("voxel_count", ctypes.c_size_t),
        ("volume_mm3", ctypes.c_double),
        ("min_x", ctypes.c_size_t),
        ("min_y", ctypes.c_size_t),
        ("min_z", ctypes.c_size_t),
        ("max_x", ctypes.c_size_t),
        ("max_y", ctypes.c_size_t),
        ("max_z", ctypes.c_size_t),
        ("is_empty", ctypes.c_int),
    ]


def _library_names() -> list[str]:
    if sys.platform == "darwin":
        return ["libmedview_core.dylib"]
    if os.name == "nt":
        return ["medview_core.dll"]
    return ["libmedview_core.so"]


def _find_library() -> Path | None:
    explicit = os.environ.get("MEDVIEW_CORE_LIBRARY")
    candidates = [Path(explicit)] if explicit else []
    root = Path(__file__).resolve().parents[3]
    for name in _library_names():
        candidates.extend([root / "build" / name, root / "build" / "Release" / name])
    return next((path for path in candidates if path.is_file()), None)


def native_available() -> bool:
    return _find_library() is not None


def mask_metrics(mask: NDArray[np.uint8], spacing: tuple[float, float, float]) -> MaskMetrics:
    contiguous = np.ascontiguousarray(mask, dtype=np.uint8)
    path = _find_library()
    if path is None:
        points = np.argwhere(contiguous > 0)
        bounds = None
        if len(points):
            bounds = (
                (int(points[:, 0].min()), int(points[:, 0].max())),
                (int(points[:, 1].min()), int(points[:, 1].max())),
                (int(points[:, 2].min()), int(points[:, 2].max())),
            )
        count = int(np.count_nonzero(contiguous))
        return MaskMetrics(count, count * float(np.prod(spacing)), bounds, "python-fallback")
    lib = ctypes.CDLL(str(path))
    func = lib.medview_mask_metrics
    func.argtypes = [
        ndpointer(dtype=np.uint8, flags="C_CONTIGUOUS"),
        *([ctypes.c_size_t] * 3),
        *([ctypes.c_double] * 3),
        ctypes.POINTER(_CMetrics),
    ]
    func.restype = ctypes.c_int
    result = _CMetrics()
    rc = func(contiguous, *contiguous.shape, *spacing, ctypes.byref(result))
    if rc != 0:
        raise RuntimeError("Native mask measurement rejected invalid input")
    bounds = (
        None
        if result.is_empty
        else (
            (result.min_x, result.max_x),
            (result.min_y, result.max_y),
            (result.min_z, result.max_z),
        )
    )
    return MaskMetrics(result.voxel_count, result.volume_mm3, bounds, "cpp")


def threshold_mask(volume: NDArray[np.float32], threshold: float) -> NDArray[np.uint8]:
    contiguous = np.ascontiguousarray(volume, dtype=np.float32)
    path = _find_library()
    if path is None:
        return (contiguous >= threshold).astype(np.uint8)
    output = np.empty(contiguous.shape, dtype=np.uint8)
    lib = ctypes.CDLL(str(path))
    func = lib.medview_threshold_mask
    func.argtypes = [
        ndpointer(dtype=np.float32, flags="C_CONTIGUOUS"),
        ndpointer(dtype=np.uint8, flags="C_CONTIGUOUS"),
        ctypes.c_size_t,
        ctypes.c_float,
    ]
    func.restype = ctypes.c_size_t
    func(contiguous, output, contiguous.size, threshold)
    return output
