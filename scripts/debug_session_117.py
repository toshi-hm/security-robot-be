
import sys
import os
from sqlalchemy import text
from dotenv import load_dotenv

sys.path.append(os.getcwd())
load_dotenv()
if os.getenv('DATABASE_URL'):
    os.environ['DATABASE_URL'] = os.getenv('DATABASE_URL').replace("@postgres:", "@localhost:")

from app.db.session import SessionLocal

def debug_117():
    with SessionLocal() as session:
        # Check count
        res = session.execute(text("SELECT COUNT(*) FROM environmentstate WHERE session_id = 117"))
        count = res.scalar()
        print(f"Session 117 Row Count: {count}")
        
        # Check non-null rewards
        res = session.execute(text("SELECT COUNT(*) FROM environmentstate WHERE session_id = 117 AND reward_received IS NOT NULL"))
        nn_count = res.scalar()
        print(f"Non-Null Reward Count: {nn_count}")
        
        # Check sample
        if count > 0:
            pass
            
        # Inspect tables again to be sure
        from sqlalchemy import inspect
        from app.db.database import sync_engine
        
        inspector = inspect(sync_engine)
        tables = inspector.get_table_names()
        print(f"Visible Tables: {tables}")
        
        # Inspect trainingmetric
        print("--- Table: trainingmetric ---")
        columns = inspector.get_columns("trainingmetric")
        for col in columns:
            print(f"  {col['name']}: {col['type']}")

        # Query metrics for job 117
        # Assuming FK is job_id or training_job_id. 
        # Check columns above to decide. But for now query * with limit
        try:
             # Try job_id first, if fails try training_job_id based on typical conventions
             # Or just check cols
             fk_col = "job_id"
             for col in columns:
                 if "job" in col['name']: fk_col = col['name']
             
             print(f"Using FK column: {fk_col}")
             
             res = session.execute(text(f'SELECT * FROM trainingmetric WHERE {fk_col} = 117 ORDER BY episode ASC LIMIT 5'))
             rows = res.fetchall()
             if rows:
                 print(f"Found {len(rows)} metrics for Job 117:")
                 for r in rows:
                     print(r)
             else:
                 print("No metrics found for Job 117.")
                 
        except Exception as e:
            print(f"Error querying trainingmetric: {e}")

if __name__ == "__main__":
    debug_117()
