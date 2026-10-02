from __future__ import annotations

from medview.demo import generate_synthetic_volume
from medview.io import load_nifti
from medview.models import ViewPlane
from medview.ui.rendering import extract_slice, paint_mask, render_png


def test_three_planes_and_render(tmp_path):
    volume = load_nifti(generate_synthetic_volume(tmp_path / "demo.nii.gz"))
    assert extract_slice(volume.voxels, ViewPlane.AXIAL, 1).shape == (112, 112)
    assert extract_slice(volume.voxels, ViewPlane.SAGITTAL, 1).shape == (80, 112)
    assert extract_slice(volume.voxels, ViewPlane.CORONAL, 1).shape == (80, 112)
    assert render_png(volume, ViewPlane.AXIAL, 40, 40, 400).startswith(b"\x89PNG")


def test_manual_paint_and_erase(tmp_path):
    volume = load_nifti(generate_synthetic_volume(tmp_path / "demo.nii.gz"))
    paint_mask(volume, ViewPlane.AXIAL, 40, 0.5, 0.5, 5, 1)
    assert volume.mask.sum() > 0
    paint_mask(volume, ViewPlane.AXIAL, 40, 0.5, 0.5, 10, 0)
    assert volume.mask.sum() == 0
