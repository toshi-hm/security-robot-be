
import sys
import os
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import text
from dotenv import load_dotenv

sys.path.append(os.getcwd())
env_path = os.path.join(os.getcwd(), '.env')
load_dotenv(env_path)

if os.getenv('DATABASE_URL'):
    os.environ['DATABASE_URL'] = os.getenv('DATABASE_URL').replace("@postgres:", "@localhost:")

from app.db.database import sync_engine

# Settings
GRID_SIZE = 20
OUTPUT_DIR = "../masterpj-tex/Figures"
# Ensure output dir exists
# Actually user said "masterpj-tex/Figures" relative to project root? 
# Current CWD is usually project root or scripts dir? 
# I will use absolute path to be safe.
OUTPUT_PATH = "/home/hama/work/master/masterpj-tex/Figures/intro_trajectories.png"
OUTPUT_DIR_ABS = os.path.dirname(OUTPUT_PATH)
if not os.path.exists(OUTPUT_DIR_ABS):
    os.makedirs(OUTPUT_DIR_ABS, exist_ok=True)

# Styling
sns.set_theme(style="white")
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.size'] = 14

def get_episode_data(session_id, episode):
    with sync_engine.connect() as conn:
        query = text("""
            SELECT step, robots, obstacles, robot_x, robot_y
            FROM environmentstate
            WHERE session_id = :sid AND episode = :ep
            ORDER BY step
            LIMIT 2000 
        """)
        # Limit 2000 just in case, though Ep 50 should be full 4000. 
        # Plotting 4000 points might be heavy but manageable. 
        # Let's take every 2nd or 4th point if too dense? Or just all. 
        # User wants "trajectory". 
        
        df = pd.read_sql(query, conn, params={"sid": session_id, "ep": episode})
        df = df.drop_duplicates(subset=['step'])
        return df

def parse_robots(row, n_robots):
    # Returns list of (x,y)
    raw = row['robots']
    if raw:
        # JSON list of dicts or list of lists
        if isinstance(raw, str):
            data = json.loads(raw)
        else:
            data = raw
            
        # Extract x,y
        res = []
        for i in range(n_robots):
            if i < len(data):
                # Check dict or list
                if isinstance(data[i], dict):
                    res.append((data[i]['x'], data[i]['y']))
                elif isinstance(data[i], list):
                    res.append((data[i][0], data[i][1]))
        return res
    else:
        # Fallback for N=1 using robot_x/y columns if robots is null
        return [(row['robot_x'], row['robot_y'])]

def plot_intro_figure():
    # Session 116 (N=1), Ep 50
    # Session 119 (N=4), Ep 50
    
    print("Fetching data...")
    df1 = get_episode_data(116, 50)
    df4 = get_episode_data(119, 50)
    
    if df1.empty or df4.empty:
        print("Error: content empty.")
        if df1.empty: print("Session 116 Ep 50 empty")
        if df4.empty: print("Session 119 Ep 50 empty")
        return

    fig, axes = plt.subplots(1, 2, figsize=(12, 6))
    
    # Define plot helper
    def plot_on_ax(ax, df, n_robots, title_label):
        # Grid
        ax.set_xlim(-0.5, GRID_SIZE-0.5)
        ax.set_ylim(-0.5, GRID_SIZE-0.5)
        ax.set_xticks(np.arange(0, GRID_SIZE, 5))
        ax.set_yticks(np.arange(0, GRID_SIZE, 5))
        ax.grid(True, color='lightgray', linestyle='--', alpha=0.5)
        ax.set_aspect('equal')
        ax.invert_yaxis() # Top-left origin
        
        # Title and Labels
        ax.set_title(title_label, fontsize=16)
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        
        # Obstacles (from Step 0)
        # Parse obstacles
        raw_obs = df.iloc[0]['obstacles']
        if isinstance(raw_obs, str): obs_grid = json.loads(raw_obs)
        else: obs_grid = raw_obs
        
        ox, oy = [], []
        # Support 2D grid list
        if isinstance(obs_grid, list) and isinstance(obs_grid[0], list):
             for r, row in enumerate(obs_grid):
                 for c, val in enumerate(row):
                     if val == 1: # 1 is obstacle
                         ox.append(c)
                         oy.append(r)
        
        ax.scatter(ox, oy, c='black', marker='s', s=40, label='Obstacle' if n_robots==1 else "")
        
        # Trajectories
        colors = ['blue', 'red', 'green', 'purple']
        
        paths = {i: {'x': [], 'y': []} for i in range(n_robots)}
        
        for idx, row in df.iterrows():
            # Skip heavy density? 
            # if idx % 2 != 0: continue 
            
            coords = parse_robots(row, n_robots)
            for r_i, (rx, ry) in enumerate(coords):
                paths[r_i]['x'].append(rx)
                paths[r_i]['y'].append(ry)
        
        from matplotlib.collections import LineCollection
        import matplotlib.colors as mcolors
                
        for r_i in range(n_robots):
            px = paths[r_i]['x']
            py = paths[r_i]['y']
            if not px: continue
            
            print(f"Robot {r_i} Start: ({px[0]}, {py[0]}) Steps: {len(px)}")
            
            # --- Gradient Alpha Logic ---
            # Create segments: (x0,y0)->(x1,y1), (x1,y1)->(x2,y2)...
            points = np.array([px, py]).T.reshape(-1, 1, 2)
            segments = np.concatenate([points[:-1], points[1:]], axis=1)
            
            # Prepare colors with alpha/transparency gradient
            n_segs = len(segments)
            base_rgb = mcolors.to_rgb(colors[r_i % len(colors)])
            
            # Alpha from 0.1 to 1.0
            alphas = np.linspace(0.1, 1.0, n_segs)
            
            # Combine into RGBA
            # shape (N, 4)
            rgba = np.zeros((n_segs, 4))
            rgba[:, 0:3] = base_rgb
            rgba[:, 3] = alphas
            
            lc = LineCollection(segments, colors=rgba, linewidths=1.5)
            ax.add_collection(lc)
            # -----------------------------
            
            # Start
            ax.scatter(px[0], py[0], c=colors[r_i], marker='o', s=80, edgecolors='white', zorder=10, label='Start' if n_robots==1 and r_i==0 else "")
            
            # End
            ax.scatter(px[-1], py[-1], c=colors[r_i], marker='D', s=80, edgecolors='white', zorder=10, label='End' if n_robots==1 and r_i==0 else "")


    # Plot (a) Single Agent
    plot_on_ax(axes[0], df1, 1, "(a)")
    
    # Plot (b) Multi Agent (N=4)
    plot_on_ax(axes[1], df4, 4, "(b)")
    
    plt.tight_layout()
    print(f"Saving to {OUTPUT_PATH}")
    plt.savefig(OUTPUT_PATH, dpi=300, bbox_inches='tight')
    plt.close()

if __name__ == "__main__":
    plot_intro_figure()
