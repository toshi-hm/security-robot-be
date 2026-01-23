
import sys
import os
import pandas as pd
import numpy as np
import json
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
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
GRID_SIZE = 20

def plot_heatmaps():
    print("Generating Placement Heatmaps...")
    
    # 1. First Pass: Find Global Max for uniform scaling
    global_max = 0
    
    # We will store data to avoid re-querying
    session_grids = {}
    
    with sync_engine.connect() as conn:
        for n_robots, sess_id in SESSION_IDS.items():
            query = text("""
                SELECT episode, step, robots
                FROM environmentstate
                WHERE session_id = :sid
            """)
            df = pd.read_sql(query, conn, params={"sid": sess_id})
            
            if df.empty:
                continue

            df_starts = df.sort_values('step').groupby('episode').first().reset_index()
            grid_counts = np.zeros((GRID_SIZE, GRID_SIZE))
            
            total_positions = 0
            for _, row in df_starts.iterrows():
                robots = row['robots']
                if isinstance(robots, str):
                    robots = json.loads(robots)
                if robots:
                    for r in robots:
                        x = int(r['x'])
                        y = int(r['y'])
                        if 0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE:
                            grid_counts[y, x] += 1
                            total_positions += 1
            
            local_max = np.max(grid_counts)
            if local_max > global_max:
                global_max = local_max
                
            session_grids[n_robots] = {
                "counts": grid_counts,
                "total": total_positions,
                "unique": np.count_nonzero(grid_counts)
            }

    # Ensure reasonable min vmax if data is sparse (e.g. at least 3)
    # But for accurate comparison, use actual global max.
    vmax_val = max(global_max, 1)
    print(f"Global Max Overlap: {vmax_val} (Used for VMAX)")

    # 2. Second Pass: Plotting
    fig, axes = plt.subplots(1, 4, figsize=(20, 5))
    plt.subplots_adjust(wspace=0.3)
    
    for idx, n_robots in enumerate(sorted(SESSION_IDS.keys())):
        ax = axes[idx]
        if n_robots not in session_grids:
            ax.text(0.5, 0.5, "No Data", ha='center')
            continue
            
        data = session_grids[n_robots]
        grid_counts = data["counts"]
        
        masked_counts = np.ma.masked_where(grid_counts == 0, grid_counts)
        cmap = plt.cm.Reds
        cmap.set_bad(color='white')
        
        # Use uniform vmin/vmax
        im = ax.imshow(masked_counts, cmap=cmap, origin='upper', interpolation='nearest', vmin=0, vmax=vmax_val)
        
        ax.set_title(f"{n_robots} Robot{'s' if n_robots > 1 else ''}")
        ax.set_xticks(range(0, GRID_SIZE, 5))
        ax.set_yticks(range(0, GRID_SIZE, 5))
        ax.grid(which='both', color='gray', linestyle='-', linewidth=0.5, alpha=0.3)
        
        # Colorbar
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        
        print(f"  Plotted N={n_robots}: Max={np.max(grid_counts)}, Total={data['total']}, Unique={data['unique']}")

    output_path = "report/result/thesis_experiment/figures/placement_heatmaps.png"
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Saved figure to {output_path}")

if __name__ == "__main__":
    plot_heatmaps()
