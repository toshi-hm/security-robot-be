#!/usr/bin/env python3
"""HTTP health check helper for docker-compose services."""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request


def main() -> int:
  url = os.getenv("HEALTHCHECK_URL", "http://localhost:8000/api/v1/health")
  timeout_raw = os.getenv("HEALTHCHECK_TIMEOUT", "5")

  try:
    timeout = float(timeout_raw)
  except ValueError:
    print(
      f"Invalid HEALTHCHECK_TIMEOUT value '{timeout_raw}', defaulting to 5 seconds.",
      file=sys.stderr,
    )
    timeout = 5.0

  try:
    with urllib.request.urlopen(url, timeout=timeout) as response:
      if response.status != 200:
        print(
          f"Health check failed: unexpected status code {response.status} for {url}",
          file=sys.stderr,
        )
        return 1
  except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
    print(f"Health check failed for {url}: {exc}", file=sys.stderr)
    return 1
  except Exception as exc:  # pragma: no cover - defensive fallback
    print(f"Unexpected error while checking {url}: {exc}", file=sys.stderr)
    return 1

  return 0


if __name__ == "__main__":
  sys.exit(main())
