
import sys
import os
import pandas as pd
import numpy as np
from sqlalchemy import text
from scipy import stats
from dotenv import load_dotenv

sys.path.append(os.getcwd())
env_path = os.path.join(os.getcwd(), '.env')
load_dotenv(env_path)

if os.getenv('DATABASE_URL'):
    os.environ['DATABASE_URL'] = os.getenv('DATABASE_URL').replace("@postgres:", "@localhost:")

from app.db.database import sync_engine

SESSION_ID = 116 # N=1
GRID_SIZE = 20

def get_data():
    print(f"Analyzing Placement Insight for Session {SESSION_ID} (N=1)...")
    
    with sync_engine.connect() as conn:
        # Check columns
        print("EnvState Cols:", pd.read_sql(text("SELECT * FROM environmentstate LIMIT 1"), conn).columns.tolist())
        
        # Assuming 'robots' is the column
        # Check total rows
        cnt = pd.read_sql(text(f"SELECT count(*) as c FROM environmentstate WHERE session_id = {SESSION_ID}"), conn).iloc[0]['c']
        print(f"Total EnvState Rows for 116: {cnt}")

        # Find min step per episode
        query_pos = text("""
            SELECT t1.episode, t1.robots
            FROM environmentstate t1
            INNER JOIN (
                SELECT episode, MIN(step) as min_step
                FROM environmentstate
                WHERE session_id = :sid
                GROUP BY episode
            ) t2 ON t1.episode = t2.episode AND t1.step = t2.min_step
            WHERE t1.session_id = :sid
            ORDER BY t1.episode
        """)
        df_pos = pd.read_sql(query_pos, conn, params={"sid": SESSION_ID})
        
        # 2. Get Rewards
        # We MUST use the same job/session as positions.
        # Session 116.
        job_id = 116
        query_rew = text("SELECT episode, reward FROM trainingmetric WHERE job_id = :jid ORDER BY episode")
        df_rew = pd.read_sql(query_rew, conn, params={"jid": job_id})
        
        # Helper to check another session
        # Trying Job 77
        check_sid = 77
        print(f"\n--- Checking Job/Session {check_sid} ---")
        
        # Pos
        query_pos77 = text("""
            SELECT t1.episode, t1.robots
            FROM environmentstate t1
            INNER JOIN (
                SELECT episode, MIN(step) as min_step
                FROM environmentstate
                WHERE session_id = :sid
                GROUP BY episode
            ) t2 ON t1.episode = t2.episode AND t1.step = t2.min_step
            WHERE t1.session_id = :sid
            ORDER BY t1.episode
        """)
        df_pos77 = pd.read_sql(query_pos77, conn, params={"sid": check_sid})
        
        # Rew
        query_rew77 = text("SELECT episode, reward FROM trainingmetric WHERE job_id = :jid ORDER BY episode")
        df_rew77 = pd.read_sql(query_rew77, conn, params={"jid": check_sid})
        
        if not df_pos77.empty and not df_rew77.empty:
            df77 = pd.merge(df_pos77, df_rew77, on='episode')
            if not df77.empty:
                 start_data77 = []
                 center = 9.5
                 for idx, row in df77.iterrows():
                    # Parse simplified
                    raw = row['robots']
                    if isinstance(raw, str): p = json.loads(raw)
                    else: p = raw
                    if not p: continue
                    if isinstance(p[0], dict): x,y = p[0]['x'], p[0]['y']
                    else: x,y = p[0][0], p[0][1]
                    dist = np.sqrt((x-center)**2 + (y-center)**2)
                    start_data77.append({'dist':dist, 'reward':row['reward']})
                 
                 stats77 = pd.DataFrame(start_data77)
                 if len(stats77) > 1:
                     corr77, p77 = stats.pearsonr(stats77['dist'], stats77['reward'])
                     print(f"Job 77 Correlation: r = {corr77:.3f} (p = {p77:.3f})")
        
        # Back to main
        print("\n--- Main Session 116 ---")
        print(f"Rewards for Job {job_id}: {len(df_rew)} rows")
        
        if df_rew.empty:
             print("CRITICAL: No rewards for Session 116. Cannot calculate correlation.")
             return
            
        print(f"Pos Rows: {len(df_pos)}, Rew Rows: {len(df_rew)}")
        
        # Merge
        df = pd.merge(df_pos, df_rew, on='episode')
        
        if df.empty:
            print("No merged data.")
            return

        # Parse Positions
        # robot_positions is JSON string or list.
        # N=1, so take first robot.
        import json
        
        start_data = []
        center = (GRID_SIZE - 1) / 2
        
        unique_pos = set()
        
        for idx, row in df.iterrows():
            raw_pos = row['robots']
            if isinstance(raw_pos, str):
                pos_list = json.loads(raw_pos)
            else:
                pos_list = raw_pos
                
            # robot 0
            # format usually [{'id':0, 'x':.., 'y':..}] or [[x,y]]?
            # Let's check data format by printing one if needed.
            # Assuming list of dicts based on previous work.
            if isinstance(pos_list, list) and len(pos_list) > 0:
                if isinstance(pos_list[0], dict):
                    x = pos_list[0]['x']
                    y = pos_list[0]['y']
                else:
                    # [[x,y]]
                    x = pos_list[0][0]
                    y = pos_list[0][1]
            else:
                continue

            unique_pos.add((x,y))
            
            dist = np.sqrt((x - center)**2 + (y - center)**2)
            start_data.append({
                'episode': row['episode'],
                'x': x,
                'y': y,
                'dist': dist,
                'reward': row['reward']
            })
            
        if len(start_data) > 0:
             stats_df = pd.DataFrame(start_data)
             
             # Max Reward
             max_row = stats_df.loc[stats_df['reward'].idxmax()]
             print(f"\nMax Reward Ep {max_row['episode']}: Pos({max_row['x']},{max_row['y']}) Dist={max_row['dist']:.2f}, Rew={max_row['reward']:.0f}")
             
             # Min Reward
             min_row = stats_df.loc[stats_df['reward'].idxmin()]
             print(f"Min Reward Ep {min_row['episode']}: Pos({min_row['x']},{min_row['y']}) Dist={min_row['dist']:.2f}, Rew={min_row['reward']:.0f}")
             
             correlation, p_value = stats.pearsonr(stats_df['dist'], stats_df['reward'])
             print(f"Correlation (Dist vs Reward): r = {correlation:.3f} (p = {p_value:.3f})")
        
        if len(start_data) > 0:
             print(f"Unique Start Positions: {len(unique_pos)} / {len(stats_df)} episodes")
             
             # Check duplicates
             from collections import Counter
             all_pos_tuples = [(r['x'], r['y']) for r in start_data]
             counts = Counter(all_pos_tuples)
             duplicates = {k: v for k,v in counts.items() if v > 1}
             print("Duplicates:", duplicates)
        
        # Late Phase Stats (Reward Std)
        # Episodes 41-50
        late_df = stats_df[stats_df['episode'] >= 41]
        mean_rew = late_df['reward'].mean()
        std_rew = late_df['reward'].std()
        cv_rew = (std_rew / mean_rew) * 100
        
        print(f"Late Phase (Ep 41-50):")
        print(f"  Mean Reward: {mean_rew:.1f}")
        print(f"  Std Reward: {std_rew:.1f}")
        print(f"  CV (Std/Mean): {cv_rew:.2f}%")

if __name__ == "__main__":
    get_data()
