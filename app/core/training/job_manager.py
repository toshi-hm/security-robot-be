class JobManager:
  async def enqueue(self, payload: dict) -> dict:
    return {'job_id': 'job-1', 'payload': payload}


job_manager = JobManager()
