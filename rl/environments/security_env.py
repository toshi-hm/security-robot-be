class SecurityEnvironment:
  def reset(self) -> dict:
    return {'state': 'reset'}

  def step(self, action: int) -> tuple[dict, float, bool, dict]:
    return {'state': 'next'}, 0.0, False, {}
