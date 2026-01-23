
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

INPUT_FILE = "multi_agent_threat_data.json"
OUTPUT_DIR = "report/result/thesis_experiment/figures"
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_FILE = f"{OUTPUT_DIR}/multi_agent_threat_trend.png"

def moving_average(data, window_size):
    return pd.Series(data).rolling(window=window_size, min_periods=1).mean().tolist()

def plot_threat_trend():
    if not os.path.exists(INPUT_FILE):
        print(f"File not found: {INPUT_FILE}")
        return

    with open(INPUT_FILE, 'r') as f:
        all_data = json.load(f)

    plt.figure(figsize=(10, 6))
    
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
        threats = data['threats']
        
        # 5-Ep MA
        ma_threats = moving_average(threats, 5)
        
        # Limit to 50 episodes
        limit = 50
        ep_plot = np.array(episodes[:limit])
        ma_plot = np.array(ma_threats[:limit])
        
        label = f"{robots} Robots"
        plt.plot(ep_plot, ma_plot, color=color, label=label, linewidth=2)
        
        # Linear Regression (Least Squares)
        # Choosing what to fit: user said "minimum square method regression line".
        # Fitting to the MA data is smoother and consistent with what is shown.
        # Fitting to raw data is also valid.
        # Given "regression line" usually implies fitting the scatter, but here we show MA.
        # I'll fit to the MA points to match the visual trend unless raw is preferred.
        # Actually, fitting to raw data is scientifically better. 
        # But for visual "trendline" on a chart showing MA, fitting MA is often used.
        # I'll fit to the PLOTTED data (MA) to avoid confusion if raw noisy data pulls the line weirdly.
        
        # Calculate fit
        # We need clean data (no NaNs). Pandas rolling handles NaNs but output might have them if window logic fails? min_periods=1 handles it.
        
        if len(ep_plot) > 1:
             m, c = np.polyfit(ep_plot, ma_plot, 1)
             # Plot regression line as dashed thin line
             plt.plot(ep_plot, m*ep_plot + c, color=color, linestyle='--', linewidth=1.5, alpha=0.7)

    plt.xlabel("Episode")
    plt.ylabel("Average Threat Level")
    # No title
    plt.xlim(0, 50)
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.7)
    
    plt.tight_layout()
    plt.savefig(OUTPUT_FILE, dpi=300)
    print(f"Saved plot to {OUTPUT_FILE}")

if __name__ == "__main__":
    plot_threat_trend()
