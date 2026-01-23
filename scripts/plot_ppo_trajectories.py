
import json
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import os

# Set style
sns.set_theme(style="white")
plt.rcParams['font.family'] = 'DejaVu Sans'

OUTPUT_DIR = "report/result/thesis_experiment/figures"
os.makedirs(OUTPUT_DIR, exist_ok=True)

GRID_SIZE = 20

def load_all_eps(filename):
    if not os.path.exists(filename):
        print(f"File not found: {filename}")
        return None
    
    data = []
    current_ep = []
    with open(filename, 'r') as f:
        for line in f:
            try:
                rec = json.loads(line)
                if not current_ep:
                    current_ep.append(rec)
                else:
                    if rec['episode'] != current_ep[0]['episode']:
                        data.append(current_ep)
                        current_ep = [rec]
                    else:
                        current_ep.append(rec)
            except:
                pass
    if current_ep:
        data.append(current_ep)
    return data

def plot_agent_subplots(agent_name, episodes):
    if not episodes:
        print(f"No data for {agent_name}")
        return

    # 5 rows x 10 cols = 50 plots
    rows = 5
    cols = 10
    fig, axes = plt.subplots(rows, cols, figsize=(25, 12.5))
    axes = axes.flatten()
    
    print(f"Plotting {agent_name} ({len(episodes)} episodes)...")

    for i, ax in enumerate(axes):
        if i < len(episodes):
            ep_data = episodes[i]
            ep_data.sort(key=lambda x: x['step'])
            
            # Setup Grid
            ax.set_xlim(-0.5, GRID_SIZE-0.5)
            ax.set_ylim(-0.5, GRID_SIZE-0.5)
            ax.set_xticks([]) # Hide ticks for cleanliness
            ax.set_yticks([])
            ax.set_title(f"Ep {ep_data[0]['episode']}", fontsize=8)
            ax.set_aspect('equal')
            ax.invert_yaxis()
            
            # Draw Obstacles (from first frame)
            # Handle potential numpy serialization diffs or lists
            obs = ep_data[0].get('obstacles', [])
            if obs:
                # If wrapped in list/array
                # Just iterate 2D
                ox = []
                oy = []
                for y, row in enumerate(obs):
                    for x, is_obs in enumerate(row):
                        if is_obs:
                            ox.append(x)
                            oy.append(y)
                ax.scatter(ox, oy, c='black', marker='s', s=10)
            
            # Draw Path
            xs = [r['robot_x'] for r in ep_data]
            ys = [r['robot_y'] for r in ep_data]
            ax.plot(xs, ys, color='red', alpha=0.7, linewidth=0.8) # PPO red
            
            # Draw Start
            ax.scatter(xs[0], ys[0], c='green', marker='o', s=15, zorder=10)
            
        else:
            ax.axis('off')

    plt.suptitle(f"{agent_name} Trajectories (Session 116)", fontsize=16)
    plt.tight_layout()
    output_path = f"{OUTPUT_DIR}/ppo_trajectories_116_50grid.png"
    plt.savefig(output_path, dpi=150)
    print(f"Saved to {output_path}")
    plt.close(fig)

def plot_ppo_trajectories():
    # Load PPO Eval
    ppo_eps = load_all_eps("trajectory_session_116.jsonl")
    plot_agent_subplots("PPO", ppo_eps)

if __name__ == "__main__":
    plot_ppo_trajectories()
