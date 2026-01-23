
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import json
import matplotlib.ticker as ticker

# Configuration
MONITOR_FILE = "monitor_n1.monitor.csv"
TRAJECTORY_FILE = "trajectory_n1.jsonl"
OUTPUT_DIR = "report/result/thesis_experiment/figures"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Plot Styling
sns.set_theme(style="whitegrid")
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.size'] = 11

def load_monitor_data(filename):
    df = pd.read_csv(filename, skiprows=1)
    df['episode'] = df.index + 1
    # Rolling mean for coverage
    df['ma_coverage'] = df['coverage_ratio'].rolling(window=5, min_periods=1).mean()
    return df

def load_trajectory_data(filename):
    data = []
    MAX_STEPS = 4000
    try:
        with open(filename, 'r') as f:
            for line in f:
                try:
                    record = json.loads(line)
                    # We only need enough to identify completion
                    # Optimization: Filter by coverage >= 0.999 while reading? 
                    # No, need step info.
                    if record.get("coverage_ratio", 0) >= 0.999:
                         data.append({
                            "episode": record.get("episode"), # This might be wrong in raw, check
                            "step": record.get("step")
                        })
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        return pd.DataFrame()
    
    df = pd.DataFrame(data)
    if df.empty:
        return df

    # Correct Episode Logic
    df['episode'] = (df['step'] // MAX_STEPS) + 1
    df['step_in_episode'] = df['step'] % MAX_STEPS
    
    # Find min step for each episode
    coverage_times = df.groupby('episode')['step_in_episode'].min().reset_index()
    coverage_times.columns = ['episode', 'steps_to_complete']
    
    # Merge with full episode range (1-50)
    all_episodes = pd.DataFrame({'episode': range(1, 51)})
    result_df = pd.merge(all_episodes, coverage_times, on='episode', how='left')
    
    # MA
    result_df['ma_steps'] = result_df['steps_to_complete'].rolling(window=5, min_periods=1).mean()
    
    return result_df

def main():
    if not os.path.exists(MONITOR_FILE):
        print(f"Error: {MONITOR_FILE} not found")
        return

    # Load Data
    monitor_df = load_monitor_data(MONITOR_FILE)
    step_df = load_trajectory_data(TRAJECTORY_FILE)
    
    # Setup Figure: 1 row, 2 columns
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # --- Plot (a) Coverage Ratio ---
    ax1 = axes[0]
    sns.lineplot(data=monitor_df, x='episode', y='coverage_ratio', color='green', alpha=0.3, label='Actual', ax=ax1)
    sns.lineplot(data=monitor_df, x='episode', y='ma_coverage', color='orange', linewidth=2.5, label='5-Episode MA', ax=ax1)
    
    ax1.set_xlabel('Episode')
    ax1.set_ylabel('Coverage Ratio')
    ax1.set_title('(a)', loc='center', y=1.02) # Subplot title
    ax1.set_ylim(0.9, 1.0) # Requested limit
    ax1.set_xlim(0, 50)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='lower right')
    
    # --- Plot (b) Steps to 100% ---
    ax2 = axes[1]
    if not step_df.empty:
        sns.scatterplot(data=step_df, x='episode', y='steps_to_complete', color='cornflowerblue', alpha=0.6, label='Steps to 100%', ax=ax2)
        sns.lineplot(data=step_df, x='episode', y='ma_steps', color='blue', linewidth=2.5, label='5-Episode MA', ax=ax2)
        
        # Stats annotation
        mean_steps = step_df['steps_to_complete'].mean()
        min_steps = step_df['steps_to_complete'].min()
        stats_text = f"Mean: {mean_steps:.0f}\nMin: {min_steps:.0f}"
        ax2.text(0.95, 0.95, stats_text, transform=ax2.transAxes, ha='right', va='top', 
                 bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    ax2.set_xlabel('Episode')
    ax2.set_ylabel('Steps to 100% Coverage')
    ax2.set_title('(b)', loc='center', y=1.02) # Subplot title
    ax2.set_ylim(0, 4200)
    ax2.set_xlim(0, 50)
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='upper right')

    plt.tight_layout()
    
    output_path = f"{OUTPUT_DIR}/thesis_single_coverage_combined.png"
    plt.savefig(output_path, dpi=300)
    print(f"Saved {output_path}")

if __name__ == "__main__":
    main()
