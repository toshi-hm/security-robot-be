from collections.abc import Awaitable, Callable
from typing import Any

WebSocketHandler = Callable[[dict[str, Any]], Awaitable[None]]
