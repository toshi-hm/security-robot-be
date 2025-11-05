"""Testing utilities for controlling time-dependent helpers."""

from __future__ import annotations

from collections import deque
from datetime import datetime

import pytest


def set_time_sequence(
    monkeypatch: pytest.MonkeyPatch,
    module: object,
    *timestamps: datetime,
) -> None:
    """Override ``utcnow`` in ``module`` so calls return ``timestamps`` in order."""

    values = deque(timestamps)

    def _utcnow() -> datetime:
        if not values:
            raise AssertionError("utcnow called more times than expected")
        if len(values) == 1:
            return values[0]
        return values.popleft()

    monkeypatch.setattr(module, "utcnow", _utcnow)
