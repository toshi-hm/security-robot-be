
import json
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd
import os

# Set style
sns.set_theme(style="whitegrid") # Use grid for better readability of curves
plt.rcParams['font.family'] = 'DejaVu Sans'

INPUT_FILE = "multi_agent_rewards_117_118_119.json"
OUTPUT_DIR = "report/result/thesis_experiment/figures"
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_FILE = f"{OUTPUT_DIR}/multi_agent_reward_curve.png"

def moving_average(data, window_size):
    return pd.Series(data).rolling(window=window_size, min_periods=1).mean().tolist()

def plot_rewards():
    if not os.path.exists(INPUT_FILE):
        print(f"File not found: {INPUT_FILE}")
        return

    with open(INPUT_FILE, 'r') as f:
        all_data = json.load(f)

    plt.figure(figsize=(10, 6))
    
    # Sort keys to ensure legend order 2 -> 3 -> 4 ? Or just iterating is fine
    # key is session_id string (json uses strings for keys)
    
    # Map for easy sort
    sessions = []
    for sid, data in all_data.items():
        data['session_id'] = sid
        sessions.append(data)
    
    sessions.sort(key=lambda x: x['robots'])
    
    for data in sessions:
        robots = data['robots']
        color = data['color'] # user specified: blue, green, red
        episodes = data['episodes']
        rewards = data['rewards']
        
        # Calculate 5-episode MA
        ma_rewards = moving_average(rewards, 5)
        
        label = f"{robots} Robots"
        plt.plot(episodes, ma_rewards, color=color, label=label, linewidth=2)
        
        # Optional: plot raw data faintly? User asked for "reward's transition (5 episode moving average)", usually implies just MA line.
        # plt.plot(episodes, rewards, color=color, alpha=0.2)

    plt.xlabel("Episode")
    plt.ylabel("Cumulative Reward (5-Ep Moving Avg)")
    # plt.title("Reward Trends in Multi-Agent Training")
    plt.xlim(0, 50)
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.7)
    
    plt.savefig(OUTPUT_FILE, dpi=300)
    print(f"Saved plot to {OUTPUT_FILE}")

if __name__ == "__main__":
    plot_rewards()
