from __future__ import annotations

import json

import nibabel as nib
import numpy as np
import pytest

from medview.demo import generate_synthetic_volume
from medview.io import export_mask, load_nifti
from medview.models import MedViewError
from medview.processing import mask_metrics, threshold_mask


def test_synthetic_load_process_export_round_trip(tmp_path):
    source = generate_synthetic_volume(tmp_path / "source.nii.gz")
    volume = load_nifti(source)
    assert volume.voxels.shape == (112, 112, 80)
    assert volume.metadata.spacing_mm == pytest.approx((0.8, 0.8, 1.5))

    volume.mask = threshold_mask(volume.voxels, 250.0)
    metrics = mask_metrics(volume.mask, volume.metadata.spacing_mm)
    assert metrics.voxel_count > 0
    assert metrics.volume_mm3 == pytest.approx(metrics.voxel_count * 0.8 * 0.8 * 1.5)

    mask_path, metadata_path = export_mask(volume, tmp_path / "export")
    exported = np.asarray(nib.load(mask_path).dataobj)
    assert np.array_equal(exported, volume.mask)
    metadata = json.loads(metadata_path.read_text())
    assert metadata["mask"]["voxel_count"] == metrics.voxel_count
    assert "not for clinical diagnosis" in metadata["disclaimer"]


def test_rejects_non_3d_nifti(tmp_path):
    path = tmp_path / "4d.nii.gz"
    nib.save(nib.Nifti1Image(np.zeros((2, 2, 2, 2)), np.eye(4)), path)
    with pytest.raises(MedViewError, match="3D"):
        load_nifti(path)


def test_metrics_empty_mask():
    result = mask_metrics(np.zeros((2, 3, 4), dtype=np.uint8), (1.0, 2.0, 3.0))
    assert result.voxel_count == 0
    assert result.bounds is None
