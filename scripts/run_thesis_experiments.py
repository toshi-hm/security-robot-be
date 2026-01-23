
import gymnasium as gym
import numpy as np
import pandas as pd
"""
# 内容
修士論文(Chapter 6)の再現実験を実行するスクリプト。
ロボット台数 N=1, 2, 3, 4 の各条件について、PPOアルゴリズムによる学習を順次実行する。

# どこで何のために必要なのか
- 実験データの生成: 論文に掲載するグラフや表の元データを生成するために使用する。
- 実行場所: `security-robot-be` ルートディレクトリ
- コマンド: `python scripts/run_thesis_experiments.py`

# 入力データ・ファイル
- なし (スクリプト内でパラメータを定義)
  - Max Steps: 4000
  - Total Timesteps: 200,000
  - Grid: 20x20 Standard

# 出力データ・ファイル
- `monitor_n{N}.monitor.csv`: 学習曲線データ(報酬, 長さ, 脅威度, カバレッジなど)
- `trajectory_n{N}.jsonl`: ロボットの移動軌跡データ(各ステップの座標, 状態)
"""

import os
import sys
import argparse
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.monitor import Monitor

# Add app to path to import SecurityEnvironment
sys.path.append(os.getcwd())
from rl.environments.security_env import SecurityEnvironment

import json
from stable_baselines3.common.callbacks import BaseCallback

class TrajectoryRecorderCallback(BaseCallback):
    def __init__(self, filename: str, verbose: int = 0):
        super().__init__(verbose)
        self.filename = filename
        self.file_handle = open(filename, "w")
        self.step_count = 0
        self.episode_count = 1

    def _on_step(self) -> bool:
        # Access the real environment
        # SB3 wraps env in DummyVecEnv -> Monitor -> SecurityEnvironment
        # We need to dig down
        env = self.training_env.envs[0].unwrapped
        
        # Build state dict (schema matches EnvironmentState DB table roughly)
        # Note: We save a dict, import script will map to DB model
        state = {
            "step": self.step_count,
            "episode": self.episode_count,
            "robot_x": env.robot_x, # Primary robot (for simple legacy check)
            "robot_y": env.robot_y,
            "robot_positions": env.robot_positions, # Multi-agent
            "robot_directions": env.robot_directions,
            "battery_levels": env.battery_levels,
            "is_charging_list": env.is_charging_list,
            "threat_levels": env.threat_levels, # 2D array
            "obstacles": env.obstacles,
            "coverage_ratio": env._get_info().get("coverage_ratio", 0.0),
            "charging_stations": env.charging_stations,
            "action": None, 
            "reward": None 
        }
        
        # Save to file (JSONL)
        self.file_handle.write(json.dumps(state) + "\n")
        
        self.step_count += 1
        return True
        
    def _on_rollout_end(self) -> None:
        pass
        
    def _on_step_end(self, _locals, _globals) -> None:
        # Check for done to increment episode
        if 'dones' in _locals and _locals['dones'][0]:
            self.episode_count += 1

    def close(self):
        self.file_handle.close()

def run_experiment(num_robots: int):
    print(f"Starting Experiment: {num_robots} Robots (With Trajectory Recording)...")
    
    # Thesis Configuration
    env_config = {
        "width": 20,
        "height": 20,
        "num_robots": num_robots,
        "revisit_window": 100,      # Thesis Request
        "revisit_penalty": 0.05,
        "exploration_bonus": 1.0,
        "max_episode_steps": 4000,
        "reward_normalization_mode": "mean"
    }
    
    # Wrap in Monitor to capture info keywords (coverage_ratio, etc) in rollout logs
    monitor_path = f"monitor_n{num_robots}"
    trajectory_path = f"trajectory_n{num_robots}.jsonl"
    
    env = SecurityEnvironment(**env_config)
    env = Monitor(env, filename=monitor_path, info_keywords=("coverage_ratio", "average_threat_level"))
    
    model = PPO(
        "MlpPolicy", 
        env, 
        verbose=1,
        learning_rate=0.0003,
        n_steps=2048,
        batch_size=64,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        n_epochs=10,
        device="cpu", # Force CPU
        tensorboard_log="./tensorboard_logs/"
    )
    
    recorder = TrajectoryRecorderCallback(filename=trajectory_path)
    
    # Train
    try:
        model.learn(total_timesteps=200_000, callback=recorder)
    finally:
        recorder.close()
        
    print(f"Finished Experiment: {num_robots} Robots")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--robots", type=int, required=True, help="Number of robots")
    args = parser.parse_args()
    
    run_experiment(args.robots)
