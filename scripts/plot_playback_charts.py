

"""
# 内容
学習ログ(CSV)から、報酬・カバレッジ・脅威度の推移グラフ(学習曲線)を生成するスクリプト。
シングルエージェント用とマルチエージェント用の各指標について、生データと移動平均をプロットする。

# どこで何のために必要なのか
- グラフ生成: 論文Chapter 6のFigure 6.1, 6.3, 6.4, 6.6, 6.7, 6.8などを生成するために使用する。
- 実行場所: `security-robot-be` ルートディレクトリ
- コマンド: `python scripts/plot_playback_charts.py`

# 入力データ・ファイル
- `monitor_n{N}.monitor.csv`: 学習ログ (N=1, 2, 3, 4)

# 出力データ・ファイル
- `report/result/thesis_experiment/figures/thesis_single_*.png/svg`: シングルエージェント用グラフ
- `report/result/thesis_experiment/figures/thesis_multi_*.png/svg`: マルチエージェント用グラフ
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import sys

# Set style
sns.set_theme(style="whitegrid")
plt.rcParams['font.family'] = 'DejaVu Sans'

# Output directory
OUTPUT_DIR = "report/result/thesis_experiment/figures"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def load_data():
    dfs = {}
    for n in [1, 2, 3, 4]:
        filename = f"monitor_n{n}.monitor.csv"
        if os.path.exists(filename):
             # Monitor CSV has header on line 2 (1-indexed), so skiprows=1 skips line 1 (metadata)
             df = pd.read_csv(filename, skiprows=1)
             
             # Rename columns for consistency
             # r=Reward, l=Length, t=Time (since start)
             if 'r' in df.columns:
                 df['reward'] = df['r']
             if 't' in df.columns:
                 df['timestep'] = df['t']
                 
             # info_keywords
             if 'average_threat_level' in df.columns:
                 df['threat_level_avg'] = df['average_threat_level']
             
             # Episode Count: reset_index gives 0, 1, 2... add 1
             df['episode_count'] = df.index + 1
             df['num_robots'] = n
             
             dfs[n] = df
        else:
            print(f"Warning: {filename} not found")
    return dfs

def plot_single_agent_thesis(df_dict):
    """
    Generate charts for Single Agent (N=1)
    """
    if 1 not in df_dict:
        print("No Single Agent data found.")
        return

    df_single = df_dict[1].copy().sort_values('timestep')

    # Calculate 5-Episode Moving Averages
    # Since data is logged every 2048 steps, and episode is 4000 steps,
    # 1 episode is approx 2 data points.
    # Window=5 episodes => Window=10 data points approx.
    window_size = 10 
    
    df_single['ma_coverage'] = df_single['coverage_ratio'].rolling(window=window_size, min_periods=1).mean()
    df_single['ma_reward'] = df_single['reward'].rolling(window=window_size, min_periods=1).mean()
    df_single['ma_threat'] = df_single['threat_level_avg'].rolling(window=window_size, min_periods=1).mean()

    # 1. Coverage
    plt.figure(figsize=(8, 5))
    sns.lineplot(data=df_single, x='episode_count', y='coverage_ratio', color='green', alpha=0.3, label='Actual')
    sns.lineplot(data=df_single, x='episode_count', y='ma_coverage', color='orange', linewidth=2.5, label='5-Episode MA')
    plt.xlabel('Episode')
    plt.ylabel('Coverage Ratio')
    plt.ylim(0.9, 1.0)
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/thesis_single_coverage_new.svg")
    plt.savefig(f"{OUTPUT_DIR}/thesis_single_coverage_new.png")
    plt.close()

    # 2. Reward
    plt.figure(figsize=(8, 5))
    sns.lineplot(data=df_single, x='episode_count', y='reward', color='cornflowerblue', alpha=0.3, label='Actual')
    sns.lineplot(data=df_single, x='episode_count', y='ma_reward', color='darkblue', linewidth=2.5, label='5-Episode MA')
    plt.xlabel('Episode')
    plt.ylabel('Accumulated Reward')
    plt.xlim(0, 50)
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/thesis_single_reward_new.svg")
    plt.savefig(f"{OUTPUT_DIR}/thesis_single_reward_new.png")
    plt.close()

    # 3. Threat
    plt.figure(figsize=(8, 5))
    sns.lineplot(data=df_single, x='episode_count', y='threat_level_avg', color='lightcoral', alpha=0.3, label='Actual')
    sns.lineplot(data=df_single, x='episode_count', y='ma_threat', color='darkred', linewidth=2.5, label='5-Episode MA')
    plt.xlabel('Episode')
    plt.ylabel('Average Threat Level')
    plt.xlim(0, 50)
    plt.ylim(0, 1.0)
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/thesis_single_threat_new.svg")
    plt.savefig(f"{OUTPUT_DIR}/thesis_single_threat_new.png")
    plt.close()

def plot_multi_agent_thesis(df_dict):
    """
    Generate charts for Multi Agent (N=2,3,4)
    """
    multi_dfs = []
    for n in [2, 3, 4]:
        if n in df_dict:
            multi_dfs.append(df_dict[n])
            
    if not multi_dfs:
        print("No Multi Agent data found.")
        return
        
    df_multi = pd.concat(multi_dfs)
    df_multi = df_multi.sort_values(['num_robots', 'timestep'])
    
    # Calculate MA
    window_size = 10
    df_multi['ma_coverage'] = df_multi.groupby('num_robots')['coverage_ratio'].transform(lambda x: x.rolling(window=window_size, min_periods=1).mean())
    df_multi['ma_reward'] = df_multi.groupby('num_robots')['reward'].transform(lambda x: x.rolling(window=window_size, min_periods=1).mean())
    df_multi['ma_threat'] = df_multi.groupby('num_robots')['threat_level_avg'].transform(lambda x: x.rolling(window=window_size, min_periods=1).mean())

    palette = {2: 'blue', 3: 'green', 4: 'red'}

    # 1. Coverage
    plt.figure(figsize=(8, 5))
    sns.lineplot(data=df_multi, x='episode_count', y='ma_coverage', hue='num_robots', palette=palette, linewidth=2.5)
    plt.xlabel('Episode')
    plt.ylabel('Coverage Ratio (5-MA)')
    plt.xlim(0, 50)
    plt.ylim(0.0, 1.05)
    plt.legend(title='Robots')
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/thesis_multi_coverage_new.svg")
    plt.savefig(f"{OUTPUT_DIR}/thesis_multi_coverage_new.png")
    plt.close()

    # 2. Reward
    plt.figure(figsize=(8, 5))
    sns.lineplot(data=df_multi, x='episode_count', y='ma_reward', hue='num_robots', palette=palette, linewidth=2.5)
    plt.xlabel('Episode')
    plt.ylabel('Accumulated Reward (5-MA)')
    plt.xlim(0, 50)
    plt.legend(title='Robots')
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/thesis_multi_reward_new.svg")
    plt.savefig(f"{OUTPUT_DIR}/thesis_multi_reward_new.png")
    plt.close()

    # 3. Threat
    plt.figure(figsize=(8, 5))
    sns.lineplot(data=df_multi, x='episode_count', y='ma_threat', hue='num_robots', palette=palette, linewidth=2.5)
    plt.xlabel('Episode')
    plt.ylabel('Average Threat Level (5-MA)')
    plt.xlim(0, 50)
    plt.ylim(0, 1.0)
    plt.legend(title='Robots')
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/thesis_multi_threat_new.svg")
    plt.savefig(f"{OUTPUT_DIR}/thesis_multi_threat_new.png")
    plt.close()

    print(f"Thesis plots saved to {OUTPUT_DIR}")

def plot_single_agent_reward_curve_figure61(df_dict):
    """
    Generate Single Agent Reward Curve specifically for Figure 6.1 reproduction.
    - No Title
    - Light Blue (Raw) vs Blue (MA)
    - X axis: 0-50
    """
    if 1 not in df_dict:
        print("No Single Agent data found for Fig 6.1")
        return

    df_single = df_dict[1].copy().sort_values('timestep')
    window_size = 10 # 5 Episodes (approx)
    
    df_single['ma_reward'] = df_single['reward'].rolling(window=window_size, min_periods=1).mean()

    plt.figure(figsize=(8, 5))
    # Light blue for raw
    sns.lineplot(data=df_single, x='episode_count', y='reward', color='skyblue', alpha=0.6, label='Actual')
    # Blue for MA
    sns.lineplot(data=df_single, x='episode_count', y='ma_reward', color='blue', linewidth=2.5, label='5-Episode MA')
    
    plt.xlabel('Episode')
    plt.ylabel('Accumulated Reward')
    plt.xlim(0, 50)
    # Removing title explicitly
    plt.title("")
    
    plt.legend()
    plt.tight_layout()
    
    # Save with distinct name
    plt.savefig(f"{OUTPUT_DIR}/thesis_single_agent_reward_curve_v3.png")
    print(f"Saved {OUTPUT_DIR}/thesis_single_agent_reward_curve_v3.png")

if __name__ == "__main__":
    df_dict = load_data()
    plot_single_agent_thesis(df_dict)
    plot_multi_agent_thesis(df_dict)
    plot_single_agent_reward_curve_figure61(df_dict)
