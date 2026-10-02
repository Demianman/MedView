from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class AuditEvent:
    timestamp_utc: str
    action: str
    details: dict[str, object]


class MaskHistory:
    """Bounded in-memory mask history and traceable action log for one study."""

    def __init__(self, limit: int = 20) -> None:
        self.limit = limit
        self._undo: list[NDArray[np.uint8]] = []
        self._redo: list[NDArray[np.uint8]] = []
        self._events: list[AuditEvent] = []

    def reset(self) -> None:
        self._undo.clear()
        self._redo.clear()
        self._events.clear()

    def checkpoint(self, mask: NDArray[np.uint8], action: str, **details: object) -> None:
        self._undo.append(mask.copy())
        self._undo = self._undo[-self.limit :]
        self._redo.clear()
        self.record(action, **details)

    def record(self, action: str, **details: object) -> None:
        self._events.append(AuditEvent(datetime.now(UTC).isoformat(), action, details))

    def undo(self, current: NDArray[np.uint8]) -> NDArray[np.uint8] | None:
        if not self._undo:
            return None
        self._redo.append(current.copy())
        restored = self._undo.pop()
        self.record("undo")
        return restored

    def redo(self, current: NDArray[np.uint8]) -> NDArray[np.uint8] | None:
        if not self._redo:
            return None
        self._undo.append(current.copy())
        restored = self._redo.pop()
        self.record("redo")
        return restored

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def events(self) -> list[dict[str, object]]:
        return [asdict(event) for event in self._events]
