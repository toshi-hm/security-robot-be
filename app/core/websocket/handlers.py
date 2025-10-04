from typing import Any, Awaitable, Callable

WebSocketHandler = Callable[[dict[str, Any]], Awaitable[None]]
