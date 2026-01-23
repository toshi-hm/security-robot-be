import numpy as np

"""
# 内容
TensorboardログからPPOの内部損失（KL, Clip, Policy, Value）を抽出し、
論文用の4分割チャート画像を生成するスクリプト。

# どこで何のために必要なのか
- グラフ生成: 論文Chapter 6のFigure 6.2 (PPO損失推移) を生成するために使用する。
- 実行場所: `security-robot-be` ルートディレクトリ
- コマンド: `python scripts/plot_loss_charts_v2.py`

# 入力データ・ファイル
- `./tensorboard_logs/PPO_1/events.out.tfevents.*`: N=1の学習ログ (Tensorboard形式)

# 出力データ・ファイル
- `report/result/thesis_experiment/figures/thesis_single_agent_ppo_loss_v2.png`: 損失推移グラフ
"""

import os
import matplotlib.pyplot as plt
import seaborn as sns
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

# Set style
sns.set_theme(style="whitegrid")
plt.rcParams['font.family'] = 'DejaVu Sans'

OUTPUT_DIR = "report/result/thesis_experiment/figures"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def find_latest_log_dir(base_dir="./tensorboard_logs", prefix="PPO"):
    """
    Find the latest PPO log directory (e.g. PPO_1).
    Since we just ran the experiment, it should be the highest numbered one or specific one.
    The logs show 'Logging to ./tensorboard_logs/PPO_1'.
    We will assume PPO_1 is the target for N=1 if it's the only one or we pick the correct one.
    """
    if not os.path.exists(base_dir):
        print(f"Directory {base_dir} not found.")
        return None
        
    # List subdirs matching PPO_X
    candidates = []
    for d in os.listdir(base_dir):
        if d.startswith(prefix):
            full_path = os.path.join(base_dir, d)
            if os.path.isdir(full_path):
                candidates.append(full_path)
    
    if not candidates:
        return None
        
    # Sort by modification time to get the latest
    candidates.sort(key=os.path.getmtime, reverse=True)
    return candidates[0]

def extract_scalars(log_dir, tags):
    ea = EventAccumulator(log_dir,
        size_guidance={
            'tensors': 0,
            'images': 0,
            'scalars': 0, # 0 means load all
        })
    ea.Reload()
    
    data = {}
    for tag in tags:
        if tag in ea.Tags()['scalars']:
            events = ea.Scalars(tag)
            steps = [e.step for e in events]
            values = [e.value for e in events]
            data[tag] = (steps, values)
        else:
            print(f"Warning: Tag {tag} not found in {log_dir}")
            
    return data

def plot_loss_charts(log_dir):
    print(f"Plotting Loss Charts from {log_dir}...")
    
    tags = [
        "train/approx_kl",
        "train/clip_fraction",
        "train/policy_gradient_loss",
        "train/value_loss"
    ]
    
    data = extract_scalars(log_dir, tags)
    
    if not data:
        print("No data extracted.")
        return

    fig, axes = plt.subplots(2, 2, figsize=(10, 8))
    # Flatten axes
    axes = axes.flatten()
    
    # Plot configuration
    # (a) Approx KL
    # (b) Clip Fraction
    # (c) Policy Gradient Loss
    # (d) Value Loss
    
    plot_map = [
        {"tag": "train/approx_kl", "title": "(a)", "ylabel": "Approx KL", "color": "blue"},
        {"tag": "train/clip_fraction", "title": "(b)", "ylabel": "Clip Fraction", "color": "orange"},
        {"tag": "train/policy_gradient_loss", "title": "(c)", "ylabel": "Policy Gradient Loss", "color": "green"},
        {"tag": "train/value_loss", "title": "(d)", "ylabel": "Value Loss", "color": "red"}
    ]
    
    for i, config in enumerate(plot_map):
        ax = axes[i]
        tag = config["tag"]
        if tag in data:
            steps, values = data[tag]
            sns.lineplot(x=steps, y=values, ax=ax, color=config["color"], alpha=0.8, linewidth=1)
            
            # Formatting
            ax.set_title(config["title"], loc='center') # Title as (a)...
            ax.set_xlabel("Timesteps")
            ax.set_xlim(0, 200000)
            
            # Format X axis ticks
            ticks = np.arange(0, 200001, 50000)
            ax.set_xticks(ticks)
            ax.set_xticklabels([f"{int(t/1000)}k" if t > 0 else "0" for t in ticks])
            
            ax.set_ylabel(config["ylabel"])
            
            # Calculate Stats (Mean, Std)
            vals = np.array(values)
            print(f"Stats for {tag} ({config['ylabel']}): Mean={vals.mean():.5f}, Std={vals.std():.5f}")
            
    plt.tight_layout()
            
    plt.tight_layout()
    output_path = f"{OUTPUT_DIR}/thesis_single_agent_ppo_loss_v2.png"
    plt.savefig(output_path)
    print(f"Saved {output_path}")

if __name__ == "__main__":
    # Assuming the latest log is the N=1 single agent run we just started.
    # Note: If N=2,3,4 run *after*, the latest might be N=4.
    # We specifically want N=1 for Figure 6.2.
    # So we should look for "PPO_1" specifically?
    # run_thesis_experiments.py uses default behavior.
    # If standard env, it might reuse PPO_1 if we deleted logs?
    # I did NOT delete ./tensorboard_logs/.
    # So it might be PPO_2, PPO_3 etc if previous existed.
    # I'll hardcode or make it configurable. 
    # For now, I'll search for "PPO_1" specifically if available, or try to be smart.
    # Actually, I'll pass the dir as argument or assume "tensorboard_logs/PPO_1" for now.
    
    target_dir = "./tensorboard_logs/PPO_6"
    if not os.path.exists(target_dir):
        # Fallback to search
        target_dir = find_latest_log_dir()
        
    if target_dir:
        plot_loss_charts(target_dir)
    else:
        print("No log directory found.")
