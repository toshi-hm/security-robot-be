
import json
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd
import os

# Set style
sns.set_theme(style="whitegrid")
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.size'] = 12

INPUT_FILE = "multi_agent_coverage_data.json"
OUTPUT_DIR = "report/result/thesis_experiment/figures"
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_FILE = f"{OUTPUT_DIR}/multi_agent_coverage_combined.png"

def moving_average(data, window_size):
    return pd.Series(data).rolling(window=window_size, min_periods=1).mean().tolist()

def plot_combined_coverage():
    if not os.path.exists(INPUT_FILE):
        print(f"File not found: {INPUT_FILE}")
        return

    with open(INPUT_FILE, 'r') as f:
        all_data = json.load(f)

    # Use 2 subplots side by side
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    # Sort sessions by robot count
    sessions = []
    for sid, data in all_data.items():
        data['session_id'] = sid
        sessions.append(data)
    sessions.sort(key=lambda x: x['robots'])
    
    for data in sessions:
        robots = data['robots']
        color = data['color']
        episodes = data['episodes']
        max_coverages = data['max_coverage']
        steps_list = data['steps_to_100']
        
        label = f"{robots} Robots"
        
        # (a) Coverage Ratio Trend
        ma_coverage = moving_average(max_coverages, 5)
        # Handle None in raw data just in case, though max_cov usually float
        # If length differs, trim
        limit = 50
        ep_plot = episodes[:limit]
        ma_cov_plot = ma_coverage[:limit]
        
        ax1.plot(ep_plot, ma_cov_plot, color=color, label=label, linewidth=2)

        # (b) Steps to 100% Trend
        # Filter Nones? If step is None, it means 100% not reached. 
        # For plot, we might skip those points or interpolate?
        # MA with Nones in pandas ignores them? 
        # Lets rely on pandas rolling
        
        # We need to align steps with episodes for plotting
        # Create Series
        steps_series = pd.Series(steps_list)
        ma_steps = steps_series.rolling(window=5, min_periods=1).mean().tolist()
        
        ma_steps_plot = ma_steps[:limit]
        
        ax2.plot(ep_plot, ma_steps_plot, color=color, label=label, linewidth=2)

    # Styling Subplot (a)
    ax1.set_xlabel("Episode")
    ax1.set_ylabel("Coverage Ratio")
    ax1.set_title("(a)")
    ax1.set_xlim(0, 50)
    ax1.set_ylim(0.99, 1) # Coverage 0-1
    ax1.legend(loc='lower right')
    ax1.grid(True, linestyle='--', alpha=0.7)

    # Styling Subplot (b)
    ax2.set_xlabel("Episode")
    ax2.set_ylabel("Steps to 100% Coverage")
    ax2.set_title("(b)")
    ax2.set_xlim(0, 50)
    # y-limit auto is probably fine
    ax2.legend(loc='upper right')
    ax2.grid(True, linestyle='--', alpha=0.7)

    plt.tight_layout()
    plt.savefig(OUTPUT_FILE, dpi=300)
    print(f"Saved combined plot to {OUTPUT_FILE}")

if __name__ == "__main__":
    plot_combined_coverage()
