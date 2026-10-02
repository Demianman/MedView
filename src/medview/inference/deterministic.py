from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from medview.processing import threshold_mask


class DeterministicThresholdSegmenter:
    """Reproducible demo provider; deliberately not a trained clinical model."""

    name = "deterministic-percentile-v1"

    def predict(self, volume: NDArray[np.float32]) -> NDArray[np.uint8]:
        threshold = float(np.percentile(volume, 88.0))
        mask = threshold_mask(volume, threshold)
        # Suppress border/background components in the synthetic demo.
        mask[[0, -1], :, :] = 0
        mask[:, [0, -1], :] = 0
        mask[:, :, [0, -1]] = 0
        return mask
