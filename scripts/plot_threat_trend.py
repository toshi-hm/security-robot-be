
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from scipy import stats
import os

INPUT_FILE = "monitor_n1.monitor.csv"
OUTPUT_DIR = "report/result/thesis_experiment/figures"
os.makedirs(OUTPUT_DIR, exist_ok=True)

sns.set_theme(style="whitegrid")
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.size'] = 11

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    df = pd.read_csv(INPUT_FILE, skiprows=1)
    df['episode'] = df.index + 1
    
    # Calculate Moving Average
    df['ma_threat'] = df['average_threat_level'].rolling(window=5, min_periods=1).mean()
    
    # Calculate Regression Line
    slope, intercept, r_value, p_value, std_err = stats.linregress(df['episode'], df['average_threat_level'])
    df['regression'] = slope * df['episode'] + intercept
    
    print(f"Slope: {slope:.5f}")
    print(f"Intercept: {intercept:.5f}")

    # Plot
    plt.figure(figsize=(10, 6))
    
    # Raw Data (Light)
    sns.scatterplot(data=df, x='episode', y='average_threat_level', color='firebrick', alpha=0.3, label='Average Threat')
    
    # Moving Average (Bold)
    sns.lineplot(data=df, x='episode', y='ma_threat', color='red', linewidth=2.5, label='5-Episode MA')
    
    # Regression (Dashed)
    plt.plot(df['episode'], df['regression'], color='black', linestyle='--', alpha=0.7, label=f'Regression (slope={slope:.1e})')
    
    plt.xlabel('Episode')
    plt.ylabel('Average Threat Level')
    plt.ylim(0.5, 1.0) # Focus on the high range based on data (0.7-0.9)
    plt.xlim(0, 50)
    plt.legend(loc='upper right')
    plt.grid(True, alpha=0.3)
    
    output_path = f"{OUTPUT_DIR}/thesis_single_agent_threat_trend_v3.png"
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    print(f"Saved plot to {output_path}")

if __name__ == "__main__":
    main()
