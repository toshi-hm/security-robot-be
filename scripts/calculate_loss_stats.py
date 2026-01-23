
import sys
import os
import pandas as pd
import numpy as np
import json
from sqlalchemy import text
from dotenv import load_dotenv

sys.path.append(os.getcwd())
env_path = os.path.join(os.getcwd(), '.env')
load_dotenv(env_path)

if os.getenv('DATABASE_URL'):
    os.environ['DATABASE_URL'] = os.getenv('DATABASE_URL').replace("@postgres:", "@localhost:")

from app.db.database import sync_engine

SESSION_ID = 116 # Single Agent

def calculate_loss_stats():
    with sync_engine.connect() as conn:
        # Using Job 77 (N=1) which has metrics
        job_id = 77
        print(f"Using Job ID {job_id}")

        query = text("""
            SELECT episode, additional_metrics
            FROM trainingmetric
            WHERE job_id = :jid
            AND additional_metrics IS NOT NULL
            ORDER BY episode
        """)
        df = pd.read_sql(query, conn, params={"jid": job_id})
        
        if df.empty:
            print("No metrics data found for Session 116.")
            return

        # Parse JSON
        metrics_list = []
        for idx, row in df.iterrows():
            raw = row['additional_metrics']
            if isinstance(raw, str):
                try:
                    data = json.loads(raw)
                except:
                    continue
            elif isinstance(raw, dict):
                data = raw
            else:
                continue
            
            # Extract specific keys
            # SB3 logs might be: 'train/approx_kl', 'train/clip_fraction', etc.
            # Or just 'approx_kl'. Let's check keys on first item.
            if idx == 0:
                print("Sample Keys:", data.keys())

            item = {'episode': row['episode']}
            # Mapping
            # Check for both "train/key" and "key"
            def get_val(d, key):
                if key in d: return d[key]
                if f"train/{key}" in d: return d[f"train/{key}"]
                return None

            item['approx_kl'] = get_val(data, 'approx_kl')
            item['clip_fraction'] = get_val(data, 'clip_fraction')
            item['policy_gradient_loss'] = get_val(data, 'policy_gradient_loss')
            item['value_loss'] = get_val(data, 'value_loss')
            item['entropy_loss'] = get_val(data, 'entropy_loss')
            
            metrics_list.append(item)
        
        df_loss = pd.DataFrame(metrics_list)
        
        # Calculate Stats (Mean, Std, Max) for columns
        cols = ['approx_kl', 'clip_fraction', 'policy_gradient_loss', 'value_loss', 'entropy_loss']
        
        print("\n=== Overall Stats (Ep 1-50) ===")
        print(f"{'Metric':<25} | {'Mean':<12} | {'Std':<12} | {'Max':<12}")
        for c in cols:
            if c not in df_loss.columns or df_loss[c].isnull().all():
                print(f"{c:<25} | N/A")
                continue
            
            mean = df_loss[c].mean()
            std = df_loss[c].std()
            mx = df_loss[c].max()
            print(f"{c:<25} | {mean:<12.5f} | {std:<12.5f} | {mx:<12.5f}")

        # Initial vs Final
        # Initial: Ep 1-10
        # Final: Ep 41-50
        init_df = df_loss[(df_loss['episode'] >= 1) & (df_loss['episode'] <= 10)]
        final_df = df_loss[(df_loss['episode'] >= 41) & (df_loss['episode'] <= 50)]
        
        print("\n=== Initial (1-10) vs Final (41-50) ===")
        print(f"{'Metric':<25} | {'Init Mean':<12} | {'Init Std':<12} | {'Final Mean':<12} | {'Final Std':<12}")
        for c in cols:
            if c not in df_loss.columns: continue
            
            im = init_df[c].mean()
            istd = init_df[c].std()
            fm = final_df[c].mean()
            fstd = final_df[c].std()
            print(f"{c:<25} | {im:<12.5f} | {istd:<12.5f} | {fm:<12.5f} | {fstd:<12.5f}")

if __name__ == "__main__":
    calculate_loss_stats()
