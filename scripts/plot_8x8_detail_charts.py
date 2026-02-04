
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import math

LOG_DIR = "logs_8x8"
OUTPUT_DIR = "report/result/thesis_experiment/figures"
os.makedirs(OUTPUT_DIR, exist_ok=True)

sns.set_theme(style="whitegrid")
plt.rcParams['font.family'] = 'DejaVu Sans'

def load_data():
    # 1. Monitor (Reward, Threat, Coverage)
    monitor_path = os.path.join(LOG_DIR, "monitor.monitor.csv")
    if not os.path.exists(monitor_path):
        print(f"File not found: {monitor_path}")
        return None, None, None
        
    df_mon = pd.read_csv(monitor_path, skiprows=1)
    df_mon['episode'] = df_mon.index + 1
    df_mon['reward'] = df_mon['r']
    # Threat & Coverage mapping
    if 'average_threat_level' in df_mon.columns:
        df_mon['threat'] = df_mon['average_threat_level']
    else:
        df_mon['threat'] = 0.0
    
    if 'coverage_ratio' in df_mon.columns:
        df_mon['coverage'] = df_mon['coverage_ratio']
    else:
        df_mon['coverage'] = 0.0

    # 2. Coverage Metrics (Steps to 100%)
    cov_path = os.path.join(LOG_DIR, "coverage_metrics.csv")
    if os.path.exists(cov_path):
        df_cov = pd.read_csv(cov_path)
    else:
        df_cov = pd.DataFrame({'episode': [], 'steps_to_100': []})

    # 3. Progress (Losses)
    prog_path = os.path.join(LOG_DIR, "progress.csv")
    if os.path.exists(prog_path):
        df_prog = pd.read_csv(prog_path)
    else:
        df_prog = pd.DataFrame()
        
    return df_mon, df_cov, df_prog

def plot_charts(df_mon, df_cov, df_prog):
    if df_mon is None:
        return

    # --- 1. Average Threat Level (Scatter + MA) ---
    plt.figure(figsize=(10, 6))
    df_mon['threat_ma'] = df_mon['threat'].rolling(window=5, min_periods=1).mean()
    sns.scatterplot(data=df_mon, x='episode', y='threat', color='red', alpha=0.4, label='Values')
    sns.lineplot(data=df_mon, x='episode', y='threat_ma', color='darkred', linewidth=2, label='5-Moving Average')
    plt.xlabel('Episode')
    plt.ylabel('Average Threat Level')
    plt.title('') # No title requested
    plt.xlim(0, 50)
    plt.ylim(0, 1.05)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "8x8_ppo_threat.png"))
    plt.close()

    # --- 2. Reward (Scatter + MA) ---
    plt.figure(figsize=(10, 6))
    df_mon['reward_ma'] = df_mon['reward'].rolling(window=5, min_periods=1).mean()
    sns.scatterplot(data=df_mon, x='episode', y='reward', color='blue', alpha=0.4, label='Values')
    sns.lineplot(data=df_mon, x='episode', y='reward_ma', color='darkblue', linewidth=2, label='5-Moving Average')
    plt.xlabel('Episode')
    plt.ylabel('Accumulated Reward')
    plt.xlim(0, 50)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "8x8_ppo_reward.png"))
    plt.close()

    # --- 3. Coverage (Scatter/Line - No MA) ---
    plt.figure(figsize=(10, 6))
    # Using lineplot with markers instead of pure scatter for visibility
    sns.lineplot(data=df_mon, x='episode', y='coverage', marker='o', color='green')
    plt.xlabel('Episode')
    plt.ylabel('Coverage Ratio')
    plt.xlim(0, 50)
    plt.ylim(0, 1.05)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "8x8_ppo_coverage.png"))
    plt.close()

    # --- 4. Steps to 100% Coverage (Scatter + MA) ---
    if not df_cov.empty:
        plt.figure(figsize=(10, 6))
        # Merge if needed, but simple plot is fine
        df_cov['steps_ma'] = df_cov['steps_to_100'].rolling(window=5, min_periods=1).mean()
        sns.scatterplot(data=df_cov, x='episode', y='steps_to_100', color='purple', alpha=0.4, label='Values')
        sns.lineplot(data=df_cov, x='episode', y='steps_ma', color='indigo', linewidth=2, label='5-Moving Average')
        plt.xlabel('Episode')
        plt.ylabel('Steps to 100% Coverage')
        plt.xlim(0, 50)
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(OUTPUT_DIR, "8x8_ppo_steps_to_100.png"))
        plt.close()

    # --- 5. Losses ---
    if not df_prog.empty:
        # Map steps to Approx Episode
        # Total steps 200,000 / 50 eps = 4000 steps/ep
        # X-axis will be 'total_timesteps' / 4000
        if 'time/total_timesteps' not in df_prog.columns:
            # Maybe 'total_timesteps'? check col names
             pass
        else:
            df_prog['approx_episode'] = df_prog['time/total_timesteps'] / 4000.0
            
            # Metrics to plot
            metrics = {
                'train/approx_kl': 'Approx KL Divergence',
                'train/clip_fraction': 'Clip Fraction',
                'train/policy_gradient_loss': 'Policy Gradient Loss',
                'train/value_loss': 'Value Loss'
            }
            
            for col, label in metrics.items():
                if col in df_prog.columns:
                    plt.figure(figsize=(10, 6))
                    sns.lineplot(data=df_prog, x='approx_episode', y=col)
                    plt.xlabel('Episode')
                    plt.ylabel(label)
                    plt.xlim(0, 50)
                    plt.tight_layout()
                    safe_name = label.lower().replace(" ", "_")
                    plt.savefig(os.path.join(OUTPUT_DIR, f"8x8_ppo_loss_{safe_name}.png"))
                    plt.close()

    print(f"Charts saved to {OUTPUT_DIR}")

if __name__ == "__main__":
    m, c, p = load_data()
    plot_charts(m, c, p)
