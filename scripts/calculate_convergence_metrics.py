
import sys
import os
import pandas as pd
import numpy as np
from sqlalchemy import text
from scipy.stats import linregress
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

def calculate_metrics():
    print("Calculating Convergence Metrics...")
    
    print(f"{'N':<3} | {'90%':<4} {'95%':<4} {'99%':<4} | {'Init CV%':<8} {'Final CV%':<8} | {'Slope':<8}")
    print("-" * 70)

    with sync_engine.connect() as conn:
        for n_robots, sess_id in SESSION_IDS.items():
            query = text("""
                SELECT episode, reward
                FROM trainingmetric
                WHERE job_id = :sid
                ORDER BY episode
            """)
            df = pd.read_sql(query, conn, params={"sid": sess_id})
            
            if df.empty or len(df) < 50:
                print(f"{n_robots:<3} | Insufficient Data")
                continue
            
            # 1. Convergence Episodes
            # Target = Mean of Last 10 (41-50)
            final_df = df[(df['episode'] >= 41) & (df['episode'] <= 50)]
            target_mean = final_df['reward'].mean()
            
            # Rolling Mean (Window 5)
            df['rolling'] = df['reward'].rolling(window=5, min_periods=1).mean()
            
            def get_conv_ep(pct):
                threshold = target_mean * pct
                # Find first episode where rolling >= threshold
                # And ideally stays? Or just first hit.
                # Standard is often first hit for simple analysis.
                reached = df[df['rolling'] >= threshold]
                if not reached.empty:
                    return reached.iloc[0]['episode']
                return ">50"

            conv_90 = get_conv_ep(0.90)
            conv_95 = get_conv_ep(0.95)
            conv_99 = get_conv_ep(0.99)
            
            # 2. Coefficient of Variation (CV)
            # Init (1-10)
            init_df = df[(df['episode'] >= 1) & (df['episode'] <= 10)]
            init_limit = 10 # episodes
            
            init_mean = init_df['reward'].mean()
            init_std = init_df['reward'].std()
            init_cv = (init_std / init_mean * 100) if init_mean != 0 else 0
            
            final_mean = final_df['reward'].mean()
            final_std = final_df['reward'].std()
            final_cv = (final_std / final_mean * 100) if final_mean != 0 else 0
            
            # 3. Learning Rate (Slope)
            # Linear regression on full range (Ep 1-50)
            slope, intercept, r_value, p_value, std_err = linregress(df['episode'], df['reward'])
            
            print(f"{n_robots:<3} | {conv_90:<4} {conv_95:<4} {conv_99:<4} | {init_cv:<8.2f} {final_cv:<8.2f} | {slope:<8.0f}")

if __name__ == "__main__":
    calculate_metrics()
