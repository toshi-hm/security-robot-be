"""Lightweight stand-in for :mod:`pydantic` used in unit tests."""

from __future__ import annotations

from typing import Any


class BaseModel:
    def __init__(self, **data: Any) -> None:
        for key, value in data.items():
            setattr(self, key, value)

    def model_dump(self) -> dict[str, Any]:  # pragma: no cover - convenience method
        return dict(self.__dict__)


__all__ = ["BaseModel"]
