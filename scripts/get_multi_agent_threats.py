
import sys
import os
import pandas as pd
from sqlalchemy import text
from dotenv import load_dotenv

sys.path.append(os.getcwd())
env_path = os.path.join(os.getcwd(), '.env')
load_dotenv(env_path)

if os.getenv('DATABASE_URL'):
    os.environ['DATABASE_URL'] = os.getenv('DATABASE_URL').replace("@postgres:", "@localhost:")

from app.db.database import sync_engine

SESSION_IDS = {
    2: 117,
    3: 118
}

def get_threats():
    with sync_engine.connect() as conn:
        for n, sid in SESSION_IDS.items():
            # Get Job ID if needed or just use session_id for metrics if they align
            # Assuming sid works for metrics as per previous success
            query = text("""
                SELECT threat_level_avg
                FROM trainingmetric
                WHERE job_id = :sid
                ORDER BY episode
            """)
            df = pd.read_sql(query, conn, params={"sid": sid})
            
            if not df.empty:
                # Last 10 eps
                final_threat = df['threat_level_avg'].tail(10).mean()
                print(f"N={n} (Job {sid}): Final Threat {final_threat:.3f}")
            else:
                print(f"N={n} (Job {sid}): No Data")

if __name__ == "__main__":
    get_threats()
