
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

with sync_engine.connect() as conn:
    # Get all jobs with num_robots=1
    query = text("SELECT id, num_robots, created_at FROM trainingjob ORDER BY id DESC")
    df = pd.read_sql(query, conn)
    print("Jobs found:")
    print(df)
    
    # Check which jobs actually have metrics
    print("\nChecking metrics counts per job:")
    jobs_with_metrics = []
    
    for jid in df['id'].tolist():
        c = pd.read_sql(text(f"SELECT count(*) as c FROM trainingmetric WHERE job_id = {jid} AND additional_metrics IS NOT NULL"), conn).iloc[0]['c']
        if c > 0:
            print(f"Job {jid} (Robots={df[df['id']==jid]['num_robots'].values[0]}): {c} rows with metrics")
            jobs_with_metrics.append(jid)
