import asyncio


async def main() -> None:
  # We need to fetch the job configuration first.
  # But run_training_job expects (session_id: int).
  # It initializes the DB session internally or uses the service?
  # Let's check training_tasks.py signature.
  # Assuming run_training_job(session_id: int)

  print("Starting debug training for Job 27...")
  try:
    # run_training_job is likely a Celery task, so it might differ.
    # But usually it calls a service method or runs the gym loop.
    # Let's inspect training_tasks.py first to be sure.
    pass
  except Exception as e:
    print(f"Error: {e}")


if __name__ == "__main__":
  asyncio.run(main())
