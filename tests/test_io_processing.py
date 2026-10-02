from __future__ import annotations

import json
from types import SimpleNamespace

import nibabel as nib
import numpy as np
import pytest

from medview.demo import generate_synthetic_volume
from medview.io import export_mask, load_nifti
from medview.io.loaders import _dicom_geometry
from medview.models import MedViewError
from medview.processing import MaskHistory, mask_metrics, threshold_mask


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


def test_dicom_patient_coordinate_affine_and_ordering():
    slices = [
        SimpleNamespace(
            ImageOrientationPatient=[1, 0, 0, 0, 1, 0],
            ImagePositionPatient=[10, 20, z],
            PixelSpacing=[0.5, 0.75],
            SliceThickness=2.0,
        )
        for z in (4.0, 0.0, 2.0)
    ]
    ordered, spacing, affine, warnings = _dicom_geometry(slices)
    assert [item.ImagePositionPatient[2] for item in ordered] == [0.0, 2.0, 4.0]
    assert spacing == pytest.approx((0.5, 0.75, 2.0))
    assert affine[:3, 0] == pytest.approx([0.0, 0.5, 0.0])
    assert affine[:3, 1] == pytest.approx([0.75, 0.0, 0.0])
    assert affine[:3, 2] == pytest.approx([0.0, 0.0, 2.0])
    assert affine[:3, 3] == pytest.approx([10.0, 20.0, 0.0])
    assert warnings == ()


def test_mask_history_undo_redo_and_audit():
    history = MaskHistory(limit=3)
    mask = np.zeros((2, 2, 2), dtype=np.uint8)
    history.checkpoint(mask, "paint", plane="axial")
    mask[0, 0, 0] = 1
    restored = history.undo(mask)
    assert restored is not None and restored.sum() == 0
    redone = history.redo(restored)
    assert redone is not None and redone.sum() == 1
    assert [event["action"] for event in history.events()] == ["paint", "undo", "redo"]


def test_export_includes_provenance_and_audit(tmp_path):
    volume = load_nifti(generate_synthetic_volume(tmp_path / "source.nii.gz"))
    _, metadata_path = export_mask(
        volume,
        tmp_path / "export",
        audit_events=[{"action": "inference"}],
        provenance={"provider": "deterministic-percentile-v1", "clinical_model": False},
    )
    metadata = json.loads(metadata_path.read_text())
    assert metadata["algorithm_provenance"]["provider"] == "deterministic-percentile-v1"
    assert metadata["audit_trail"] == [{"action": "inference"}]
