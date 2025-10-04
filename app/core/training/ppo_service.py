class PPOTrainingService:
  async def start_training(self, config: dict) -> dict:
    return {'status': 'started', 'algorithm': 'ppo', 'config': config}


ppo_service = PPOTrainingService()
