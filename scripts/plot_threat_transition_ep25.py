
import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import os

INPUT_FILE = "trajectory_n1.jsonl"
OUTPUT_DIR = "report/result/thesis_experiment/figures"
os.makedirs(OUTPUT_DIR, exist_ok=True)
TARGET_EPISODE = 25
STEPS_PER_EPISODE = 4000

# Calculate step range for Episode 25
# Ep 1: 0-3999
# Ep 25: 24 * 4000 to 25 * 4000 - 1
START_STEP = (TARGET_EPISODE - 1) * STEPS_PER_EPISODE
END_STEP = TARGET_EPISODE * STEPS_PER_EPISODE

sns.set_theme(style="whitegrid")
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.size'] = 11

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    print(f"Extracting data for Episode {TARGET_EPISODE} (Steps {START_STEP}-{END_STEP})...")
    
    data = []
    
    with open(INPUT_FILE, 'r') as f:
        # Optimization: parsing line by line, checking step immediately
        for line in f:
            try:
                # We can do a quick check if "step" is in range before full load?
                # But JSON parsing is needed anyway.
                record = json.loads(line)
                step = record.get("step")
                
                if step is None:
                    continue
                    
                if START_STEP <= step < END_STEP:
                    # Calculate average threat for this step
                    threat_grid = record.get("threat_levels")
                    if threat_grid:
                        # 2D list to flat mean
                        avg_threat = np.mean(threat_grid)
                        data.append({
                            "step_in_episode": step - START_STEP,
                            "avg_threat": avg_threat
                        })
                elif step >= END_STEP:
                    # Assumes sequential file
                    break
            except json.JSONDecodeError:
                continue

    if not data:
        print("No data found for Episode 25.")
        return

    df = pd.DataFrame(data)
    
    # Calculate Stats
    mean_val = df['avg_threat'].mean()
    min_val = df['avg_threat'].min()
    max_val = df['avg_threat'].max()
    final_val = df.iloc[-1]['avg_threat']
    
    print(f"Stats for Episode {TARGET_EPISODE}:")
    print(f"Mean: {mean_val:.4f}")
    print(f"Min: {min_val:.4f}")
    print(f"Max: {max_val:.4f}")
    print(f"Final: {final_val:.4f}")

    # Plot
    plt.figure(figsize=(10, 5))
    sns.lineplot(data=df, x='step_in_episode', y='avg_threat', color='firebrick', linewidth=1.5)
    
    plt.xlabel('Step')
    plt.ylabel('Average Threat Level')
    # plt.title(f'Threat Level Transition (Episode {TARGET_EPISODE})') # No title for thesis
    plt.ylim(0, 1.0)
    plt.xlim(0, 4000)
    plt.grid(True, alpha=0.3)
    
    output_path = f"{OUTPUT_DIR}/thesis_single_threat_transition_ep25.png"
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    print(f"Saved plot to {output_path}")

if __name__ == "__main__":
    main()
