import pandas as pd
import matplotlib.pyplot as plt
import os
from matplotlib.ticker import FuncFormatter

# Configuration
# Map RL Job IDs to Robot Counts
rl_jobs = {
    2: {"id": 56, "label": "RL (PPO)"},
    3: {"id": 55, "label": "RL (PPO)"},
    4: {"id": 57, "label": "RL (PPO)"},
    5: {"id": 58, "label": "RL (PPO)"}, # Using Job 58 for consistency
}

# Baseline configurations
baselines = ["zigzag", "spiral"]
baseline_labels = {"zigzag": "Zigzag", "spiral": "Spiral"}

ARTIFACT_DIR = "/home/hama/work/master/security-robot-be/report/result/cycle12"
CSV_DIR = "/home/hama/work/master/security-robot-be"

def load_csv(filepath):
    if not os.path.exists(filepath):
        print(f"Warning: {filepath} not found.")
        return None
    try:
        return pd.read_csv(filepath)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None

def plot_benchmark(n_robots, rl_job_info, baseline_data):
    # Create a figure with 3 subplots (Team Reward, Coverage, Threat)
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle(f"Benchmark Comparison: {n_robots} Robots", fontsize=16)
    
    metrics = [
        {"col": "estimated_team_reward", "title": "Team Reward", "ylabel": "Reward"},
        {"col": "coverage_ratio", "title": "Coverage Ratio", "ylabel": "Coverage (0-1)"},
        {"col": "threat_level_avg", "title": "Average Threat Level", "ylabel": "Threat (0-1)"}
    ]
    
    # 1. Plot RL Data
    rl_filepath = os.path.join(CSV_DIR, f"job_{rl_job_info['id']}_metrics.csv")
    rl_df = load_csv(rl_filepath)
    
    if rl_df is not None:
        for i, metric in enumerate(metrics):
            ax = axes[i]
            # Smooth RL data
            smoothed = rl_df[metric["col"]].rolling(window=10, min_periods=1).mean()
            ax.plot(rl_df["timestep"], smoothed, label=rl_job_info["label"], linewidth=2, color="blue")

    # 2. Plot Baselines
    colors = {"zigzag": "orange", "spiral": "green"}
    
    for pattern in baselines:
        df = baseline_data.get(pattern)
        if df is not None:
            for i, metric in enumerate(metrics):
                ax = axes[i]
                # Baselines don't learn, but we plot their timeline to match RL
                # Smooth heavily to show trend (or lack thereof)
                smoothed = df[metric["col"]].rolling(window=50, min_periods=1).mean()
                ax.plot(df["timestep"], smoothed, label=baseline_labels[pattern], linewidth=2, linestyle='--', color=colors[pattern])
                
                # Add mean line?
                # mean_val = df[metric["col"]].mean()
                # ax.axhline(mean_val, color=colors[pattern], linestyle=':', alpha=0.5)

    # Styling
    for i, metric in enumerate(metrics):
        ax = axes[i]
        ax.set_title(metric["title"], fontsize=12)
        ax.set_xlabel("Timesteps")
        ax.set_ylabel(metric["ylabel"])
        ax.grid(True, linestyle='--', alpha=0.7)
        ax.legend()
        
        # Format X axis
        def k_formatter(x, pos):
            return f'{int(x/1000)}k'
        ax.xaxis.set_major_formatter(FuncFormatter(k_formatter))

    output_path = os.path.join(ARTIFACT_DIR, f"benchmark_{n_robots}_robots.png")
    plt.tight_layout()
    plt.savefig(output_path, dpi=100)
    print(f"Saved {output_path}")
    plt.close()

def main():
    robots_list = [2, 3, 4, 5]
    
    for n in robots_list:
        print(f"Generating benchmark plots for {n} robots...")
        
        # Load baseline data for this N
        baseline_data = {}
        for pattern in baselines:
            filepath = os.path.join(CSV_DIR, f"baseline_{pattern}_{n}_metrics.csv")
            df = load_csv(filepath)
            if df is not None:
                baseline_data[pattern] = df
        
        if n in rl_jobs:
            plot_benchmark(n, rl_jobs[n], baseline_data)
        else:
            print(f"No RL job defined for {n} robots")

if __name__ == "__main__":
    main()
