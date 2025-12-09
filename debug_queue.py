from app.db.database import sync_engine
from app.db.session import SessionLocal
from app.models.training import TrainingJob

print(f"DB URL: {sync_engine.url}")


db = SessionLocal()
try:
  print("Querying all jobs...")
  jobs = db.query(TrainingJob).all()
  print(f"Total jobs: {len(jobs)}")
  for j in jobs:
    print(f" - {j.id}: {j.status}")
except Exception as e:
  print(f"Query Error: {e}")
finally:
  db.close()
