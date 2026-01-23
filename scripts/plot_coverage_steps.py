
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import json

# Configuration
INPUT_FILE = "trajectory_n1.jsonl"
OUTPUT_DIR = "report/result/thesis_experiment/figures"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Plot Styling
sns.set_theme(style="whitegrid")
plt.rcParams['font.family'] = 'DejaVu Sans'

def load_trajectory_data(filename):
    """
    Load trajectory data line by line to extract coverage timing.
    We don't need the full state, just episode, step, coverage_ratio.
    """
    data = []
    print(f"Loading {filename}...")
    
    with open(filename, 'r') as f:
        for line in f:
            try:
                record = json.loads(line)
                # Keep only necessary fields to save memory
                data.append({
                    "episode": record.get("episode"),
                    "step": record.get("step"),
                    "coverage_ratio": record.get("coverage_ratio")
                })
            except json.JSONDecodeError:
                continue
                
    return pd.DataFrame(data)

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    df = load_trajectory_data(INPUT_FILE)
    
    MAX_STEPS = 4000
    df['episode'] = (df['step'] // MAX_STEPS) + 1
    
    # Filter for full coverage frames (>= 0.999 is safe for 1.0)
    full_coverage_df = df[df['coverage_ratio'] >= 0.999]
    
    # Group by inferred episode and find min step relative to episode start
    # The 'step' is global. We want step within episode.
    # relative_step = global_step % 4000
    # But wait, step might not be perfectly 0-aligned if there are offset issues?
    # Assuming 0-start.
    full_coverage_df['step_in_episode'] = full_coverage_df['step'] % MAX_STEPS
    
    # We want the *first* step in the episode that reached full coverage.
    coverage_times = full_coverage_df.groupby('episode')['step_in_episode'].min().reset_index()
    coverage_times.columns = ['episode', 'steps_to_complete']
    
    # Merge with all episodes (1 to 50)
    # We ignore potential partial 51st episode if it exists.
    max_ep = df['episode'].max()
    if max_ep > 50: 
        max_ep = 50 # Cap at 50 for thesis
        
    all_episodes = pd.DataFrame({'episode': range(1, int(max_ep) + 1)})
    result_df = pd.merge(all_episodes, coverage_times, on='episode', how='left')
    
    # Provide stats
    completed_df = result_df.dropna()
    print(f"Total Episodes: {len(result_df)}")
    print(f"Completed Episodes: {len(completed_df)}")
    if not completed_df.empty:
        print(f"Mean Steps to Complete: {completed_df['steps_to_complete'].mean():.2f}")
        print(f"Min Steps to Complete: {completed_df['steps_to_complete'].min()}")
    
    # Calculate Moving Average (e.g., window=5)
    result_df['ma_steps'] = result_df['steps_to_complete'].rolling(window=5, min_periods=1).mean()

    # Plot
    plt.figure(figsize=(10, 6))
    
    # Scatter plot for actual data points
    sns.scatterplot(data=result_df, x='episode', y='steps_to_complete', color='blue', alpha=0.6, label='Steps to 100%')
    
    # Line plot for MA
    sns.lineplot(data=result_df, x='episode', y='ma_steps', color='red', linewidth=2.5, label='5-Episode MA')
    
    plt.xlabel("Episode")
    plt.ylabel("Steps to 100% Coverage")
    plt.xlim(0, 50)
    plt.ylim(0, MAX_STEPS + 200) # Slightly above max
    
    # Highlight failures? (Maybe points at top?)
    # For now, failures are NaN and won't be plotted.
    # Let's plot them as X marks at MAX_STEPS
    failures = result_df[result_df['steps_to_complete'].isna()]
    if not failures.empty:
        plt.scatter(failures['episode'], [MAX_STEPS]*len(failures), color='gray', marker='x', s=50, label='Did not complete')

    plt.legend()
    plt.tight_layout()
    
    output_path = f"{OUTPUT_DIR}/thesis_single_coverage_steps.png"
    plt.savefig(output_path)
    print(f"Saved plot to {output_path}")

if __name__ == "__main__":
    main()
