

"""
# 内容
軌跡ログ(JSONL)から、ロボットの移動軌跡図およびエピソード内の脅威度推移グラフを生成するスクリプト。
特定のエピソード(初期・中期・後期)を抽出して可視化する。

# どこで何のために必要なのか
- グラフ生成: 論文Chapter 6のFigure 6.5 (脅威度推移), 6.9 (S軌跡), 6.13 (M軌跡)などを生成するために使用する。
- 実行場所: `security-robot-be` ルートディレクトリ
- コマンド: `python scripts/plot_trajectory_charts.py`

# 入力データ・ファイル
- `trajectory_n{N}.jsonl`: 軌跡ログ (N=1, 4)

# 出力データ・ファイル
- `report/result/thesis_experiment/figures/thesis_single_trajectories.png/svg`: シングル軌跡
- `report/result/thesis_experiment/figures/thesis_multi_trajectories.png/svg`: マルチ軌跡
- `report/result/thesis_experiment/figures/thesis_single_threat_transition.png/svg`: 脅威度詳細推移
"""

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

def load_trajectory(n, episode_target=None):
    filename = f"trajectory_n{n}.jsonl"
    if not os.path.exists(filename):
        print(f"File not found: {filename}")
        return []
    
    data = []
    with open(filename, 'r') as f:
        for line in f:
            record = json.loads(line)
            # Infer episode from step (Max 4000 steps per ep)
            # record['step'] is cumulative 0, 1, ...
            inferred_ep = (record['step'] // 4000) + 1
            record['episode'] = inferred_ep
            
            # If filtering by specific episodes
            if episode_target is not None:
                if inferred_ep in episode_target:
                    data.append(record)
            else:
                data.append(record)
    return data

def calculate_avg_threat(threat_grid):
    return np.mean(threat_grid)

def plot_threat_transition_single(ep_target=47):
    print(f"Plotting Threat Transition for Single Agent Episode {ep_target}...")
    records = load_trajectory(1, [ep_target])
    if not records:
        print("No records found for threat transition.")
        return

    # Sort by step
    records.sort(key=lambda x: x['step'])
    
    # Calculate avg threat per step
    steps = []
    threats = []
    
    # Normalize steps to 0-based for this episode
    start_step = records[0]['step']
    
    for r in records:
        steps.append(r['step'] - start_step)
        threats.append(calculate_avg_threat(r['threat_levels']))
        
    plt.figure(figsize=(10, 5))
    plt.plot(steps, threats, color='darkred', linewidth=1)
    plt.xlabel('Step')
    plt.ylabel('Average Threat Level')
    plt.title(f'Threat Level Transition (Episode {ep_target})')
    plt.ylim(0, 1.0)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/thesis_single_threat_transition.svg")
    plt.savefig(f"{OUTPUT_DIR}/thesis_single_threat_transition.png")
    plt.close()

def plot_trajectories(n_robots, target_episodes, output_name):
    print(f"Plotting Trajectories for N={n_robots} (Episodes {target_episodes})...")
    
    # Load all needed episodes
    records = load_trajectory(n_robots, target_episodes)
    if not records:
        return

    # Group by episode
    ep_data = {ep: [] for ep in target_episodes}
    for r in records:
        if r['episode'] in ep_data:
            ep_data[r['episode']].append(r)
            
    # Create subplots
    num_plots = len(target_episodes)
    fig, axes = plt.subplots(1, num_plots, figsize=(4*num_plots, 4))
    if num_plots == 1:
        axes = [axes]
        
    for idx, ep in enumerate(target_episodes):
        ax = axes[idx]
        data = ep_data[ep]
        
        # Sort
        data.sort(key=lambda x: x['step'])
        
        # Limit to 1000 steps
        data = data[:1000]
        
        if not data:
            continue
            
        # Draw Grid
        ax.set_xlim(-0.5, GRID_SIZE-0.5)
        ax.set_ylim(-0.5, GRID_SIZE-0.5)
        ax.set_xticks(np.arange(0, GRID_SIZE, 5))
        ax.set_yticks(np.arange(0, GRID_SIZE, 5))
        ax.grid(True, color='lightgray', linestyle='--', alpha=0.5)
        ax.set_aspect('equal')
        ax.invert_yaxis() # Matrix coordinates (0,0 is top-left usually) -> Check thesis convention
        # Thesis: (0,0) usually top-left in programming, but plots often bottom-left.
        # Let's assume math coordinates for plotting (0,0 bottom left). 
        # But backend simulation is likely matrix (y, x).
        # Data: robot_x, robot_y.
        # To match visual expectation of a map, let's keep invert_yaxis if it matches matrix.
        # If env uses [y][x], then y=0 is top.
        
        ax.set_title(f"Episode {ep}")
        
        # Plot Trajectories
        # Handle N robots
        colors = ['blue', 'green', 'red', 'purple']
        
        # Prepare arrays for each robot
        robot_paths = {i: {'x': [], 'y': []} for i in range(n_robots)}
        
        for step_data in data:
            if 'robot_positions' in step_data and step_data['robot_positions']:
                for r_idx, (rx, ry) in enumerate(step_data['robot_positions']):
                    if r_idx < n_robots:
                        robot_paths[r_idx]['x'].append(rx)
                        robot_paths[r_idx]['y'].append(ry)
            else:
                 # Legacy fallback for N=1 if robot_positions missing
                 robot_paths[0]['x'].append(step_data['robot_x'])
                 robot_paths[0]['y'].append(step_data['robot_y'])
                 
        for r_id in range(n_robots):
            path = robot_paths[r_id]
            if not path['x']: continue
            
            # Plot line
            # Alpha gradient to show time? Just a line for now as per thesis sample description ("time corresponding to color darkness" - hard to do simply with lineplot, user used custom)
            # We'll use simple line with opacity
            ax.plot(path['x'], path['y'], color=colors[r_id], alpha=0.6, linewidth=1)
            
            # Start (Circle)
            ax.scatter(path['x'][0], path['y'][0], c=colors[r_id], marker='o', s=30, label='Start' if idx==0 else "")
            
            # End (Square)
            ax.scatter(path['x'][-1], path['y'][-1], c=colors[r_id], marker='s', s=30, label='End' if idx==0 else "")
            
        # Obstacles (from first frame)
        obs = data[0].get('obstacles', []) # List of [x, y]? Or grid?
        # Env returns dict usually or list. 
        # In EnvironmentState it's mapped.
        # Let's verify data format. "obstacles": env.obstacles -> typically set of tuples or list of lists.
        # If it's list of [x,y]:
        if obs and isinstance(obs, list):
             ox = [o[0] for o in obs]
             oy = [o[1] for o in obs]
             ax.scatter(ox, oy, c='black', marker='s', s=10)
    
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/{output_name}.svg")
    plt.savefig(f"{OUTPUT_DIR}/{output_name}.png")
    plt.close()

if __name__ == "__main__":
    # 1. Single Agent Threat Transition (Ep 47)
    plot_threat_transition_single(47)
    
    # 2. Single Agent Trajectories (Ep 1, 2, 25, 47, 50)
    plot_trajectories(1, [1, 2, 25, 47, 50], "thesis_single_trajectories")
    
    # 3. Multi Agent Trajectories (N=4) (Ep 1, 2, 25, 49, 50) - Thesis mentions N=? for trajectories?
    # Thesis 6.2.1 says "Fig 6.13: Trajectories by robot count"
    # Actually Figure 6.13 caption says: "Multi-agent trajectories (Ep 1, 2, 25, 49, 50)".
    # Usually implies just one N configuration (likely N=4 or side by side?)
    # "Figure 6.13: Trajectories for EACH robot count" -> Usually implies one row per N?
    # Section text: "Fig 6.13 shows trajectories for EACH robot count... Each figure shows Ep 1, 2..."
    # This implies 3 separate rows or 3 separate figures?
    # Current implementation in plots combines them? 
    # Let's generate for N=4 as the representative "Multi-agent" example if not specified.
    # Text says: "Figure 6.13: Multi-agent trajectories".
    # I will generate for N=4 for now to represent "Multi".
    plot_trajectories(4, [1, 2, 25, 49, 50], "thesis_multi_trajectories")
