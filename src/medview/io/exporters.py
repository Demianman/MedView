from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import nibabel as nib
import numpy as np

from medview.models import Volume


def export_mask(
    volume: Volume,
    output_dir: Path,
    stem: str = "medview_mask",
    *,
    audit_events: list[dict[str, object]] | None = None,
    provenance: dict[str, object] | None = None,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    mask_path = output_dir / f"{stem}.nii.gz"
    metadata_path = output_dir / f"{stem}.json"
    image = nib.Nifti1Image(  # type: ignore[no-untyped-call]
        volume.mask.astype(np.uint8), volume.affine
    )
    nib.save(image, str(mask_path))
    payload = {
        "format_version": "1.0",
        "created_utc": datetime.now(UTC).isoformat(),
        "disclaimer": "Educational portfolio software; not for clinical diagnosis.",
        "source": volume.metadata.as_dict(),
        "mask": {
            "labels": {"0": "background", "1": "demo region"},
            "voxel_count": int(volume.mask.sum()),
        },
        "algorithm_provenance": provenance or {"type": "manual-only", "clinical_model": False},
        "audit_trail": audit_events or [],
    }
    metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return mask_path, metadata_path
