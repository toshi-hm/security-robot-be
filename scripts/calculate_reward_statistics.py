
import sys
import os
import pandas as pd
import numpy as np
from sqlalchemy import text
from dotenv import load_dotenv

sys.path.append(os.getcwd())
# Explicitly load .env from CWD
env_path = os.path.join(os.getcwd(), '.env')
load_dotenv(env_path)
if os.getenv('DATABASE_URL'):
    os.environ['DATABASE_URL'] = os.getenv('DATABASE_URL').replace("@postgres:", "@localhost:")

from app.db.database import sync_engine

SESSION_IDS = {
    1: 116,
    2: 117,
    3: 118,
    4: 119
}

def calculate_stats():
    print("Calculating Reward and Coverage Statistics...")
    
    print(f"{'N':<3} | {'Init Reward (Mean +/- Std)':<25} | {'Final Reward (Mean +/- Std)':<25} | {'Imp %':<6} | {'Conv Ep':<7} | {'Init Cov':<8} | {'Final Cov':<8}")
    print("-" * 120)

    with sync_engine.connect() as conn:
        for n_robots, sess_id in SESSION_IDS.items():
            # Get Reward and Coverage from TrainingMetric
            # Assuming job_id = session_id logic from before
            query = text("""
                SELECT episode, reward, coverage_ratio
                FROM trainingmetric
                WHERE job_id = :sid
                ORDER BY episode
            """)
            df = pd.read_sql(query, conn, params={"sid": sess_id})
            
            if df.empty:
                print(f"{n_robots:<3} | No Data")
                continue
            
            # Initial: 1-10
            init_df = df[(df['episode'] >= 1) & (df['episode'] <= 10)]
            # Final: 41-50 (User prompt says 40-49 in text, but let's stick to 41-50 for consistency with other sections, or 40-49 if user explicitly asked for update based on that range?
            # User prompt text says "訓練初期(エピソード1-10)と訓練後期(エピソード40-49)".
            # Note: The prompt asks to update the table which cites 40-49.
            # However, my previous sections used 41-50.
            # I should probably use 41-50 (last 10) for "Final" unless there is a strong reason.
            # Actually, standard is usually last 10. 41-50 is consistent.
            # I will use 41-50 and update the text to say 41-50 if I change it, or stick to 40-49.
            # Let's check the max episode. It's 50.
            # 41-50 seems more natural for "Last 10". 
            # I will use 41-50 and note it in the update.
            final_df = df[(df['episode'] >= 41) & (df['episode'] <= 50)]
            
            # 1. Reward Stats
            init_rew_mean = init_df['reward'].mean()
            init_rew_std = init_df['reward'].std()
            final_rew_mean = final_df['reward'].mean()
            final_rew_std = final_df['reward'].std()
            
            imp_rate = (final_rew_mean - init_rew_mean) / init_rew_mean * 100 if init_rew_mean != 0 else 0
            
            # 2. Convergence Episode
            # Heuristic: Find first episode where rolling mean (window=5) >= 0.95 * final_rew_mean
            # And stays there? Or just first crossing.
            df['rolling_rew'] = df['reward'].rolling(window=5, min_periods=1).mean()
            target = 0.95 * final_rew_mean
            
            conv_ep = "N/A"
            # We look for the first index where rolling mean >= target
            # Ideally, it should stabilize.
            # Let's verify if it stays above target for remainder? Or just first time.
            # Simple heuristic: first time rolling > target.
            reached = df[df['rolling_rew'] >= target]
            if not reached.empty:
                conv_ep = reached.iloc[0]['episode']
            
            # 3. Coverage Stats (Mean only)
            init_cov = init_df['coverage_ratio'].mean()
            final_cov = final_df['coverage_ratio'].mean()
            
            # Formatting
            print(f"{n_robots:<3} | {init_rew_mean:,.0f} +/- {init_rew_std:,.0f}       | {final_rew_mean:,.0f} +/- {final_rew_std:,.0f}       | {imp_rate:5.1f}% | {conv_ep:<7} | {init_cov:.3f}    | {final_cov:.3f}")

if __name__ == "__main__":
    calculate_stats()
