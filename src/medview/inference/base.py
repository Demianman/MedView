from __future__ import annotations

from typing import Protocol

import numpy as np
from numpy.typing import NDArray


class SegmentationProvider(Protocol):
    name: str

    def predict(self, volume: NDArray[np.float32]) -> NDArray[np.uint8]: ...
