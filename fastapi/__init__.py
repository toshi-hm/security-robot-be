"""Minimal FastAPI stub providing the pieces required for unit tests."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T", bound=Callable[..., Awaitable[Any]] | Callable[..., Any])


class HTTPException(Exception):
    def __init__(self, *, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class APIRouter:
    def get(self, *args: Any, **kwargs: Any) -> Callable[[T], T]:
        def decorator(func: T) -> T:
            return func

        return decorator


status = SimpleNamespace(HTTP_404_NOT_FOUND=404)


__all__ = ["APIRouter", "HTTPException", "status"]
