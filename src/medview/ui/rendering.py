from __future__ import annotations

from io import BytesIO

import numpy as np
from PIL import Image

from medview.models import ViewPlane, Volume


def extract_slice(array: np.ndarray, plane: ViewPlane, index: int) -> np.ndarray:
    axis = {ViewPlane.SAGITTAL: 0, ViewPlane.CORONAL: 1, ViewPlane.AXIAL: 2}[plane]
    if index < 0 or index >= array.shape[axis]:
        raise IndexError(f"Slice {index} outside {plane} range")
    if axis == 0:
        return np.rot90(array[index, :, :])
    if axis == 1:
        return np.rot90(array[:, index, :])
    return np.rot90(array[:, :, index])


def render_png(
    volume: Volume, plane: ViewPlane, index: int, level: float, width: float, overlay: bool = True
) -> bytes:
    width = max(float(width), 1.0)
    image = extract_slice(volume.voxels, plane, index)
    low, high = level - width / 2, level + width / 2
    gray = np.clip((image - low) / (high - low), 0, 1)
    rgb = np.repeat((gray * 255).astype(np.uint8)[..., None], 3, axis=2)
    if overlay:
        mask = extract_slice(volume.mask, plane, index) > 0
        rgb[mask] = (0.35 * rgb[mask] + 0.65 * np.array([19, 206, 170])).astype(np.uint8)
    output = BytesIO()
    Image.fromarray(rgb).save(output, format="PNG")
    return output.getvalue()


def paint_mask(
    volume: Volume, plane: ViewPlane, index: int, u: float, v: float, radius: int, value: int
) -> None:
    axis = {ViewPlane.SAGITTAL: 0, ViewPlane.CORONAL: 1, ViewPlane.AXIAL: 2}[plane]
    view = extract_slice(volume.mask, plane, index)
    height, width = view.shape
    cx, cy = int(np.clip(u, 0, 1) * (width - 1)), int(np.clip(v, 0, 1) * (height - 1))
    yy, xx = np.ogrid[:height, :width]
    view[(xx - cx) ** 2 + (yy - cy) ** 2 <= radius**2] = value
    restored = np.rot90(view, -1)
    if axis == 0:
        volume.mask[index, :, :] = restored
    elif axis == 1:
        volume.mask[:, index, :] = restored
    else:
        volume.mask[:, :, index] = restored
