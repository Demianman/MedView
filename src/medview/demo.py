from __future__ import annotations

from pathlib import Path

import nibabel as nib
import numpy as np


def generate_synthetic_volume(path: Path, seed: int = 2027) -> Path:
    """Generate a deterministic CT-like phantom with no patient data."""
    rng = np.random.default_rng(seed)
    shape = (112, 112, 80)
    x, y, z = np.indices(shape)
    center = np.array(shape) / 2
    body = (
        ((x - center[0]) / 45) ** 2 + ((y - center[1]) / 38) ** 2 + ((z - center[2]) / 33) ** 2
    ) < 1
    organ = (((x - 61) / 20) ** 2 + ((y - 53) / 14) ** 2 + ((z - 42) / 19) ** 2) < 1
    lesion = (((x - 67) / 7) ** 2 + ((y - 49) / 6) ** 2 + ((z - 44) / 8) ** 2) < 1
    voxels = np.full(shape, -950.0, dtype=np.float32)
    voxels[body] = 35.0
    voxels[organ] = 85.0
    voxels[lesion] = 310.0
    voxels += rng.normal(0, 7, shape).astype(np.float32)
    affine = np.diag([0.8, 0.8, 1.5, 1.0])
    path.parent.mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(voxels, affine), str(path))  # type: ignore[no-untyped-call]
    return path


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    path = generate_synthetic_volume(root / "demo_data" / "synthetic_abdomen.nii.gz")
    print(f"Generated {path}")


if __name__ == "__main__":
    main()
