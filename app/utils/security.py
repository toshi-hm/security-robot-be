def allow_localhost_only(origin: str) -> bool:
  return origin.startswith("http://localhost") or origin.startswith("http://127.0.0.1")
