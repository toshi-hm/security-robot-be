
import json
import matplotlib.pyplot as plt
import numpy as np
import os
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap

# Configuration
INPUT_FILE = "../trajectory_session_116.jsonl"
OUTPUT_DIR = "../report/result/thesis_experiment/figures"
GRID_SIZE = 20

def load_data(filename, target_episodes):
    """Load trajectory data for specific episodes."""
    data_by_episode = {ep: [] for ep in target_episodes}
    
    if not os.path.exists(filename):
        print(f"Error: File {filename} not found.")
        return {}

    with open(filename, 'r') as f:
        for line in f:
            try:
                record = json.loads(line)
                # Infer episode (assuming 4000 steps per episode as per previous script logic, 
                # but let's check if 'episode' field exists explicitly)
                episode = record.get('episode')
                
                if episode is None:
                    # Fallback inference if needed, though 'episode' was in the head output
                    step = record.get('step', 0)
                    episode = (step // 4000) + 1
                
                if episode in target_episodes:
                    data_by_episode[episode].append(record)
            except json.JSONDecodeError:
                continue
                
    # Sort each episode by step
    for ep in data_by_episode:
        data_by_episode[ep].sort(key=lambda x: x['step'])
        
    return data_by_episode

def plot_trajectory(episode, records, output_path):
    """Plot trajectory for a single episode."""
    if not records:
        print(f"No records for episode {episode}")
        return

    # User request: Remove the last step as it contains the start position of the next episode
    if len(records) > 1:
        records = records[:-1]

    # Extract coordinates
    x_coords = []
    y_coords = []
    
    for r in records:
        # Support both single object format and robot_positions list
        if 'robot_positions' in r and len(r['robot_positions']) > 0:
            # Assuming single agent (id:0) as verified
            agent = next((rp for rp in r['robot_positions'] if rp['id'] == 0), r['robot_positions'][0])
            x_coords.append(agent['x'])
            y_coords.append(agent['y'])
        else:
            x_coords.append(r.get('robot_x', 0))
            y_coords.append(r.get('robot_y', 0))

    if not x_coords:
        return

    fig, ax = plt.subplots(figsize=(6, 6))
    
    # Setup Grid
    ax.set_xlim(-0.5, GRID_SIZE-0.5)
    ax.set_ylim(-0.5, GRID_SIZE-0.5)
    ax.set_xticks(np.arange(0, GRID_SIZE, 5))
    ax.set_yticks(np.arange(0, GRID_SIZE, 5))
    ax.grid(True, color='lightgray', linestyle='--', alpha=0.5)
    ax.set_aspect('equal')
    ax.invert_yaxis() # Match matrix coordinates
    
    # Plot Obstacles (from the first frame)
    first_record = records[0]
    obstacles = first_record.get('obstacles', [])
    if obstacles:
        obs_x = []
        obs_y = []
        for y, row in enumerate(obstacles):
            for x, is_obs in enumerate(row):
                if is_obs:
                    obs_x.append(x)
                    obs_y.append(y)
        ax.scatter(obs_x, obs_y, c='black', marker='s', s=100, label='Obstacle')

    # Create Line Collection for Gradient Alpha
    points = np.array([x_coords, y_coords]).T.reshape(-1, 1, 2)
    segments = np.concatenate([points[:-1], points[1:]], axis=1)
    
    # Create a colormap that is just Blue but varies in alpha is tricky with LineCollection directly
    # Easier: Use a custom colormap that goes from transparent blue to solid blue
    # Or set colors array with varying alpha
    
    num_segments = len(segments)
    colors = np.zeros((num_segments, 4))
    colors[:, 0] = 0.0 # R (Blue is 0,0,1)
    colors[:, 1] = 0.0 # G
    colors[:, 2] = 1.0 # B
    # Alpha linear space from 0.05 to 1.0
    colors[:, 3] = np.linspace(0.05, 1.0, num_segments)
    
    lc = LineCollection(segments, colors=colors, linewidths=2)
    ax.add_collection(lc)

    # Plot Start (Circle)
    ax.scatter(x_coords[0], y_coords[0], c='blue', marker='o', s=100, label='Start', zorder=10)
    
    # Plot End (Square)
    ax.scatter(x_coords[-1], y_coords[-1], c='blue', marker='s', s=100, label='End', zorder=10)

    # Labels and Title
    ax.set_title(f'Episode {episode} Trajectory')
    # ax.legend(loc='upper right') # Optional, might clutter

    # Save
    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path)
    # Also save as SVG
    plt.savefig(output_path.replace('.png', '.svg'))
    plt.close()
    print(f"Saved plot to {output_path}")

def main():
    target_episodes = [1, 50]
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(script_dir, INPUT_FILE)
    output_dir = os.path.join(script_dir, OUTPUT_DIR)

    print(f"Loading data from {input_path}...")
    data = load_data(input_path, target_episodes)

    for ep in target_episodes:
        if ep in data:
            output_filename = f"job116_episode_{ep}_trajectory.png"
            output_path = os.path.join(output_dir, output_filename)
            plot_trajectory(ep, data[ep], output_path)
        else:
            print(f"No data found for episode {ep}")

if __name__ == "__main__":
    main()
