class A3CTrainingService:
  async def start_training(self, config: dict) -> dict:
    return {'status': 'started', 'algorithm': 'a3c', 'config': config}


a3c_service = A3CTrainingService()
