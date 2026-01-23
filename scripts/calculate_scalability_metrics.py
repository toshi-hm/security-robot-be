
import sys
import os
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

sys.path.append(os.getcwd())
load_dotenv()
if os.getenv('DATABASE_URL'):
    os.environ['DATABASE_URL'] = os.getenv('DATABASE_URL').replace("@postgres:", "@localhost:")

from app.db.database import sync_engine

SESSION_IDS = {
    1: 116,
    2: 117,
    3: 118,
    4: 119
}

def calculate_scalability():
    print("Calculating Scalability Metrics (Ep 41-50)...")
    
    results = {}
    
    with sync_engine.connect() as conn:
        for n_robots, sess_id in SESSION_IDS.items():
            job_id = sess_id # Assuming job_id is same as session_id for imported data
            
            # 2. Get Metrics from TrainingMetric
            query_tm = text("""
                SELECT 
                    episode, 
                    coverage_ratio, 
                    reward, 
                    threat_level_avg
                FROM trainingmetric
                WHERE job_id = :jid 
                AND episode BETWEEN 41 AND 50
            """)
            df_tm = pd.read_sql(query_tm, conn, params={"jid": job_id})
            
            if df_tm.empty:
                print(f"N={n_robots}: No TM data.")
                avg_coverage_tm = 0
                avg_threat = 0
                avg_reward = 0
            else:
                avg_coverage_tm = df_tm['coverage_ratio'].mean()
                avg_threat = df_tm['threat_level_avg'].mean()
                avg_reward = df_tm['reward'].mean()

            # 3. Get Steps from EnvironmentState
            query_es = text("""
                SELECT 
                    episode, 
                    step, 
                    coverage_ratio
                FROM environmentstate
                WHERE session_id = :sid 
                AND episode BETWEEN 41 AND 50
                ORDER BY episode, step
            """)
            df_es = pd.read_sql(query_es, conn, params={"sid": sess_id})
            
            avg_steps = np.nan
            if not df_es.empty:
                steps_list = []
                for ep in range(41, 51):
                    ep_df = df_es[df_es['episode'] == ep]
                    if ep_df.empty: continue
                    
                    # Reached 100%?
                    reached = ep_df[ep_df['coverage_ratio'] >= 0.999]
                    if not reached.empty:
                        steps = reached.iloc[0]['step']
                        steps_list.append(steps)
                
                if steps_list:
                    avg_steps = np.mean(steps_list)

            results[n_robots] = {
                "coverage": avg_coverage_tm,
                "steps": avg_steps,
                "threat": avg_threat,
                "reward": avg_reward
            }
            
    print("\n--- Scalability Analysis Data (Ep 41-50) ---")
    print(f"{'N':<5} {'Cov(TM)':<10} {'Steps(ES)':<10} {'Threat':<10} {'Reward':<10}")
    for n, res in results.items():
        s_val = f"{res['steps']:.1f}" if not np.isnan(res['steps']) else "NaN"
        print(f"{n:<5} {res['coverage']:.4f}     {s_val:<10}      {res['threat']:.4f}     {res['reward']:.1f}")

if __name__ == "__main__":
    calculate_scalability()
