from typing import Any

class EnvironmentService:
  async def list_definitions(self) -> list[dict[str, Any]]:
    return []

  async def get_state(self, environment_id: str) -> dict[str, Any]:
    return {'environment_id': environment_id}


environment_service = EnvironmentService()
