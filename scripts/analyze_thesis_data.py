
"""
# 内容
実験結果データ(CSV/JSONL)を読み込み、論文掲載用の統計データ（平均、標準偏差、相関係数など）を計算して標準出力に表示するスクリプト。
また、初期配置位置のヒートマップ画像(`placement_heatmaps.png`)を生成する。

# どこで何のために必要なのか
- データ分析: 論文Chapter 6の表(Table 6.1, 6.4, 6.7など)や考察に必要な数値を算出するために使用する。
- グラフ生成: 配置ヒートマップ(Figure 6.10)を作成する。
- 実行場所: `security-robot-be` ルートディレクトリ
- コマンド: `python scripts/analyze_thesis_data.py`

# 入力データ・ファイル
- `monitor_n{N}.monitor.csv`: 学習ログ
- `trajectory_n{N}.jsonl`: 軌跡ログ

# 出力データ・ファイル
- `report/result/thesis_experiment/figures/placement_heatmaps.png`: 配置ヒートマップ
- 標準出力: 各種統計値
"""

import pandas as pd
import numpy as np
import json
import os
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

OUTPUT_DIR = "report/result/thesis_experiment/figures"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def load_monitor(n):
    filename = f"monitor_n{n}.monitor.csv"
    if not os.path.exists(filename):
        return None
    df = pd.read_csv(filename, skiprows=1)
    # Map columns
    # r, l, t, coverage_ratio, average_threat_level
    # Add episode number
    df['episode'] = df.index + 1
    return df

def load_trajectory_metadata(n):
    filename = f"trajectory_n{n}.jsonl"
    if not os.path.exists(filename):
        return []
    
    metadata = []
    with open(filename, 'r') as f:
        # We only need start positions (Step 0 of each episode)
        # But file is flat list of steps.
        # We need to detect episode boundaries.
        # Implemented logic: inferred_ep = (step // 4000) + 1
        # We assume step 0, 4000, 8000... are starts.
        
        for line in f:
            data = json.loads(line)
            step = data.get('step', 0)
            if step % 4000 == 0:
                # Start of episode
                ep = (step // 4000) + 1
                
                # Get start positions
                # For N=1, robot_x, robot_y
                # For N>1, robot_positions list
                
                positions = []
                if 'robot_positions' in data:
                    positions = data['robot_positions']
                else:
                    positions = [(data.get('robot_x'), data.get('robot_y'))]
                
                metadata.append({
                    'episode': ep,
                    'start_positions': positions
                })
    return metadata

def analyze_single_agent(df, traj_data):
    print("\n--- Single Agent Analysis (N=1) ---")
    
    # Table 6.1: Ep 40-49 stats
    late_df = df[(df['episode'] >= 40) & (df['episode'] <= 49)]
    print("Table 6.1 (Ep 40-49):")
    print(f"Reward: {late_df['r'].mean():.1f} +/- {late_df['r'].std():.1f}")
    print(f"Coverage: {late_df['coverage_ratio'].mean():.3f} +/- {late_df['coverage_ratio'].std():.3f}")
    if 'average_threat_level' in late_df.columns:
        print(f"Threat: {late_df['average_threat_level'].mean():.3f} +/- {late_df['average_threat_level'].std():.3f}")
    
    # Correlation (Start Pos Distance vs Reward)
    # Join df with traj_data
    # Center (10, 10). Grid 0-19? Or 1-20? Code usually 0-19. Center is 9.5, 9.5 or 10,10.
    # Thesis says "Grid center (10, 10)".
    # dist = sqrt((x-10)^2 + (y-10)^2)
    center = np.array([10, 10])
    
    dists = []
    rewards = []
    
    # Map traj episode to reward
    reward_map = df.set_index('episode')['r'].to_dict()
    
    for item in traj_data:
        ep = item['episode']
        if ep in reward_map:
            # Single agent -> 1 pos
            pos = item['start_positions'][0]
            d = np.linalg.norm(np.array(pos) - center)
            dists.append(d)
            rewards.append(reward_map[ep])
            
    if dists:
        r_val, p_val = stats.pearsonr(dists, rewards)
        print(f"\nCorrelation (Dist vs Reward): r = {r_val:.3f} (p={p_val:.3f})")
    
    # Placement Heatmap Data
    all_starts = []
    for item in traj_data:
        all_starts.extend(item['start_positions'])
    return all_starts

def analyze_multi_agent(n, df):
    print(f"\n--- Multi Agent Analysis (N={n}) ---")
    
    # Early (1-10) vs Late (40-49)
    early = df[(df['episode'] >= 1) & (df['episode'] <= 10)]
    late = df[(df['episode'] >= 40) & (df['episode'] <= 49)]
    
    print(f"Early Reward: {early['r'].mean():.1f}")
    print(f"Late Reward: {late['r'].mean():.1f}")
    
    print(f"Early Coverage: {early['coverage_ratio'].mean():.3f}")
    print(f"Late Coverage: {late['coverage_ratio'].mean():.3f}")
    
    if 'average_threat_level' in df.columns:
        print(f"Early Threat: {early['average_threat_level'].mean():.3f}")
        print(f"Late Threat: {late['average_threat_level'].mean():.3f}")

def plot_heatmaps(all_starts_dict):
    # Figure 6.10: Heatmaps for N=1,2,3,4
    fig, axes = plt.subplots(1, 4, figsize=(20, 5))
    
    for i, n in enumerate([1, 2, 3, 4]):
        ax = axes[i]
        starts = all_starts_dict.get(n, [])
        
        # Create 20x20 grid
        grid = np.zeros((20, 20))
        for (x, y) in starts:
            if 0 <= x < 20 and 0 <= y < 20:
                grid[y][x] += 1 # y is row, x is col
        
        sns.heatmap(grid, ax=ax, cmap="YlOrRd", cbar=False, linewidths=.5, linecolor='gray')
        ax.set_title(f"N={n}")
        ax.invert_yaxis() # Match coordinate system
        
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/placement_heatmaps.png")
    print(f"\nGenerated placement_heatmaps.png")

def main():
    all_starts_dict = {}
    
    for n in [1, 2, 3, 4]:
        df = load_monitor(n)
        traj = load_trajectory_metadata(n)
        
        if df is not None:
            if n == 1:
                starts = analyze_single_agent(df, traj)
                all_starts_dict[1] = starts
            else:
                analyze_multi_agent(n, df)
                # Collect starts for heatmap
                starts = []
                for item in traj:
                    starts.extend(item['start_positions'])
                all_starts_dict[n] = starts

    plot_heatmaps(all_starts_dict)

if __name__ == "__main__":
    main()
