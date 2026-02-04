
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

def analyze():
    print("Analyzing 8x8 Experiments...")
    
    # 1. Load PPO
    ppo_file = "monitor_8x8_ppo.monitor.csv"
    if os.path.exists(ppo_file):
        df_ppo = pd.read_csv(ppo_file, skiprows=1)
        df_ppo['reward'] = df_ppo['r']
        # Handle case where threat/coverage might be missing or named differently
        # Usually 'average_threat_level' and 'coverage_ratio'
        if 'average_threat_level' in df_ppo.columns:
            df_ppo['threat'] = df_ppo['average_threat_level']
        else:
            df_ppo['threat'] = 0.0
            
        if 'coverage_ratio' in df_ppo.columns:
            df_ppo['coverage'] = df_ppo['coverage_ratio']
        else:
            df_ppo['coverage'] = 0.0
            
        df_ppo['agent'] = 'PPO'
        df_ppo['episode'] = df_ppo.index + 1
    else:
        print("PPO file not found")
        df_ppo = None

    # 2. Load Baselines
    baselines = []
    for name in ['zigzag', 'spiral']:
        f = f"monitor_8x8_{name}.csv"
        if os.path.exists(f):
            df = pd.read_csv(f)
            df['reward'] = df['r']
            df['threat'] = df.get('average_threat_level', 0.0)
            df['coverage'] = df.get('coverage_ratio', 0.0)
            df['agent'] = name.capitalize()
            df['episode'] = df.index + 1
            baselines.append(df)
        else:
            print(f"{f} not found")

    if df_ppo is not None:
        # Plotting Transition (Reward and Threat)
        plt.figure(figsize=(12, 5))
        
        plt.subplot(1, 2, 1)
        sns.lineplot(data=df_ppo, x='episode', y='reward', label='PPO Raw', alpha=0.3)
        # MA
        df_ppo['reward_ma'] = df_ppo['reward'].rolling(window=5, min_periods=1).mean()
        sns.lineplot(data=df_ppo, x='episode', y='reward_ma', label='PPO MA(5)')
        
        # Add baseline averages as horizontal lines
        colors = {'Zigzag': 'green', 'Spiral': 'orange'}
        for b_df in baselines:
            name = b_df['agent'].iloc[0]
            avg_rew = b_df['reward'].mean()
            plt.axhline(y=avg_rew, color=colors.get(name, 'black'), linestyle='--', label=f'{name} Avg')
            
        plt.title('Reward Transition')
        plt.legend()
        
        plt.subplot(1, 2, 2)
        sns.lineplot(data=df_ppo, x='episode', y='threat', label='PPO Raw', alpha=0.3)
        df_ppo['threat_ma'] = df_ppo['threat'].rolling(window=5, min_periods=1).mean()
        sns.lineplot(data=df_ppo, x='episode', y='threat_ma', label='PPO MA(5)')
        
        for b_df in baselines:
            name = b_df['agent'].iloc[0]
            avg_threat = b_df['threat'].mean()
            plt.axhline(y=avg_threat, color=colors.get(name, 'black'), linestyle='--', label=f'{name} Avg')

        plt.title('Threat Level Transition')
        plt.legend()
        
        plt.tight_layout()
        plt.savefig("analysis_8x8_transition.png")
        print("Saved analysis_8x8_transition.png")

        # Comparison Table
        print("\n=== Experiment Results Comparison (8x8 Single Agent) ===")
        print(f"{'Agent':<10} | {'Reward (Avg)':<15} | {'Threat (Avg)':<15} | {'Coverage (Avg)':<15}")
        print("-" * 65)
        
        # PPO (Last 10 eps)
        last_10 = df_ppo.tail(10)
        print(f"{'PPO (End)':<10} | {last_10['reward'].mean():.1f} (+/-{last_10['reward'].std():.1f}) | {last_10['threat'].mean():.3f}           | {last_10['coverage'].mean():.3f}")
        
        # Baselines
        for b_df in baselines:
            name = b_df['agent'].iloc[0]
            print(f"{name:<10} | {b_df['reward'].mean():.1f} (+/-{b_df['reward'].std():.1f}) | {b_df['threat'].mean():.3f}           | {b_df['coverage'].mean():.3f}")
            
        # Diff Calculation
        print("\n=== Differences (PPO (End) vs Baselines) ===")
        ppo_rew = last_10['reward'].mean()
        ppo_thr = last_10['threat'].mean()
        ppo_cov = last_10['coverage'].mean()
        
        for b_df in baselines:
            name = b_df['agent'].iloc[0]
            base_rew = b_df['reward'].mean()
            base_thr = b_df['threat'].mean()
            base_cov = b_df['coverage'].mean()
            
            diff_rew = ppo_rew - base_rew
            diff_thr = ppo_thr - base_thr
            diff_cov = ppo_cov - base_cov
            
            print(f"vs {name:<7}: Reward {diff_rew:+.1f}, Threat {diff_thr:+.3f}, Coverage {diff_cov:+.3f}")

if __name__ == "__main__":
    analyze()
