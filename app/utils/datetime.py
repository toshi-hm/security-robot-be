"""Datetime utilities for timezone-aware operations."""

from datetime import datetime, timezone


def utcnow() -> datetime:
  """Return the current UTC time as a timezone-aware datetime."""
  return datetime.now(tz=timezone.utc)
