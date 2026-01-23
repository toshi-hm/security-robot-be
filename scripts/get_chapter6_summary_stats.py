
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
    1: 116, # Job ?? -> derived from prev steps, likely Job 77 for metrics? 
            # Wait, for pure Reward/Coverage/Threat columns, they ARE in the DB for Session 116 (Job 77/116 issue).
            # The 'missing data' was specifically for 'additional_metrics' (PPO internal loss).
            # Basic metrics (reward, coverage, threat) SHOULD be in `trainingmetric` for the correct job_id.
            # In step 5288, calculate_reward_statistics.py worked fine with SESSION_IDS map.
            # So I can use SESSION_IDS = {1: 116, ...} and regular query.
    1: 116,
    4: 119
}

def get_stats():
    print("Calculating Summary Stats for Chapter 6.5.1...")
    
    with sync_engine.connect() as conn:
        # Get Job IDs
        job_map = {}
        for n, sid in SESSION_IDS.items():
            # Try finding job by session_id
            # Note: In previous step `calculate_loss_stats.py` failed to find session_id column in trainingjob?
            # Step 5468 output showed `trainingjob` columns: ..., 'id', ... NO 'session_id'.
            # Ah! `trainingjob` does NOT have `session_id`?
            # Wait, `calculate_reward_statistics.py` (Step 5280) used:
            # `SELECT ... FROM trainingmetric WHERE job_id = :sid` assuming job_id=session_id.
            # And it returned data!
            # So for `trainingmetric`, `job_id` matches `session_id` (116, 117...).
            # EXCEPT for 'additional_metrics' investigation where I found Job 77?
            # Actually, `find_correct_job_id.py` (Step 5492) showed:
            # Job 119 (N=4), Job 118 (N=3), Job 117 (N=2), Job 116 (N=1).
            # BUT efficient metrics matching showed:
            # Job 77 (N=1): 401 rows.
            # Job 53/52 (N=3).
            # Step 5492 output also showed:
            # "Job 116 (Robots=1) ... checking metrics ... count=???" - It didn't print count for 116, meaning 0?
            # "Job 77 (Robots=1): 401 rows with metrics".
            #
            # RE-READING Step 5288 output:
            # "N=1 | 68,240... | 76,837..." -> It DID find data for 116.
            # So `trainingmetric` has rows with `job_id=116` that contain reward/coverage?
            # But `additional_metrics` was missing?
            # Let's verify counts for 116 again to be 100% sure.
            # I will check `job_id=116` for reward/coverage.
            pass
        
        # We will use the IDs that worked for Reward Stats: 116, 117, 118, 119.
        # If they worked then, they work now.
        
        for n, jid in SESSION_IDS.items():
            query = text("""
                SELECT episode, reward, coverage_ratio, threat_level_avg
                FROM trainingmetric
                WHERE job_id = :jid
                ORDER BY episode
            """)
            df = pd.read_sql(query, conn, params={"jid": jid})
            
            if df.empty:
                print(f"N={n} (Job {jid}): No Data")
                continue
                
            # Init (1-10) and Final (41-50)
            init_df = df[(df['episode'] >= 1) & (df['episode'] <= 10)]
            final_df = df[(df['episode'] >= 41) & (df['episode'] <= 50)]
            
            print(f"\n--- N={n} (Job {jid}) ---")
            
            # Reward
            init_rw = init_df['reward'].mean()
            final_rw = final_df['reward'].mean()
            imp_rate = (final_rw - init_rw) / init_rw * 100
            print(f"Reward: Init {init_rw:.0f} -> Final {final_rw:.0f} (Imp {imp_rate:.1f}%)")
            
            # Coverage
            init_cov_mean = init_df['coverage_ratio'].mean()
            init_cov_std = init_df['coverage_ratio'].std()
            final_cov_mean = final_df['coverage_ratio'].mean()
            final_cov_std = final_df['coverage_ratio'].std()
            cov_std_red = (1 - (final_cov_std / init_cov_std)) * 100 if init_cov_std > 0 else 0
            
            print(f"Coverage: Final Mean {final_cov_mean:.3f}")
            print(f"Coverage Std: Init {init_cov_std:.4f} -> Final {final_cov_std:.4f} (Red {cov_std_red:.1f}%)")
            
            # Threat
            final_threat = final_df['threat_level_avg'].mean()
            print(f"Final Threat: {final_threat:.3f}")

if __name__ == "__main__":
    get_stats()
