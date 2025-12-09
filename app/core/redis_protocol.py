"""Protocol definition for Redis publisher to avoid circular imports."""

from typing import Any, Protocol


class RedisPublisher(Protocol):
  """Minimal Redis publisher protocol used for type checking."""

  def publish(self, channel: str, message: str) -> Any:
    """Publish a message to the given channel."""
