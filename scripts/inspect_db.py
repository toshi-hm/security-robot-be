
import sys
import os
from sqlalchemy import inspect, text
from dotenv import load_dotenv

# Add app to path
sys.path.append(os.getcwd())

# Load .env BEFORE importing app modules so settings get correct values
load_dotenv()

# Override host to localhost for local script execution
if os.getenv('DATABASE_URL'):
    os.environ['DATABASE_URL'] = os.getenv('DATABASE_URL').replace("@postgres:", "@localhost:")

# Verify if DATABASE_URL is loaded
print(f"DATABASE_URL (mod for script): {os.getenv('DATABASE_URL')}")

from app.db.database import sync_engine
from app.db.session import SessionLocal

def inspect_db():
    print("Connecting to DB (sync_engine)...")
    inspector = inspect(sync_engine)
    
    tables = inspector.get_table_names()
    print("Tables:", tables)
    
    for table in tables:
        print(f"\n--- Table: {table} ---")
        columns = inspector.get_columns(table)
        for col in columns:
            print(f"  {col['name']}: {col['type']}")

    # Check for Job 116
    with SessionLocal() as session:
        try:
             # jobs table name might be different, let's look at the output first
             # But assuming 'jobs' or 'training_jobs' based on models
             if "jobs" in tables:
                 result = session.execute(text("SELECT * FROM jobs WHERE id = 116"))
                 row = result.fetchone()
                 if row:
                     print("\nFound Job 116 in 'jobs':", row)
                 else:
                     print("\nJob 116 not found in 'jobs'.")
             elif "training_sessions" in tables:
                  result = session.execute(text("SELECT * FROM training_sessions WHERE id = 116"))
                  row = result.fetchone()
                  if row:
                     print("\nFound Session 116 in 'training_sessions':", row)
                  
        except Exception as e:
            print(f"\nError querying jobs: {e}")

if __name__ == "__main__":
    inspect_db()
