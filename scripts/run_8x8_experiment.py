
import gymnasium as gym
import numpy as np
import pandas as pd
import os
import sys
import argparse
import json
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.monitor import Monitor

# Add app to path to import SecurityEnvironment
sys.path.append(os.getcwd())
try:
    from rl.environments.security_env import SecurityEnvironment
except ImportError:
    sys.path.append(os.path.join(os.getcwd(), ".."))
    from rl.environments.security_env import SecurityEnvironment

class TrajectoryRecorderCallback(BaseCallback):
    def __init__(self, filename: str, verbose: int = 0):
        super().__init__(verbose)
        self.filename = filename
        self.file_handle = open(filename, "w")
        self.step_count = 0
        self.episode_count = 1

    def _on_step(self) -> bool:
        env = self.training_env.envs[0].unwrapped
        
        state = {
            "step": self.step_count,
            "episode": self.episode_count,
            "robot_x": env.robot_x, 
            "robot_y": env.robot_y,
            "robot_positions": env.robot_positions,
            "robot_directions": env.robot_directions,
            "battery_levels": env.battery_levels,
            "is_charging_list": env.is_charging_list,
            "threat_levels": env.threat_levels if isinstance(env.threat_levels, list) else env.threat_levels.tolist(),
            "obstacles": env.obstacles,
            "coverage_ratio": env._get_info().get("coverage_ratio", 0.0),
            "charging_stations": env.charging_stations,
            "average_threat_level": env._get_info().get("average_threat_level", 0.0),
            "action": None, 
            "reward": None 
        }
        
        self.file_handle.write(json.dumps(state) + "\n")
        
        self.step_count += 1
        return True
        
    def _on_rollout_end(self) -> None:
        pass
        
    def _on_step_end(self, _locals, _globals) -> None:
        if 'dones' in _locals and _locals['dones'][0]:
            self.episode_count += 1

    def close(self):
        self.file_handle.close()

def run_experiment():
    print("Starting 8x8 Single Agent Experiment (PPO)...")
    
    # 8x8 Configuration
    env_config = {
        "width": 8,
        "height": 8,
        "num_robots": 1,
        "revisit_window": 100,
        "revisit_penalty": 0.05,
        "exploration_bonus": 1.0,
        "max_episode_steps": 4000,
        "reward_normalization_mode": "mean"
    }
    
    monitor_path = "monitor_8x8_ppo"
    trajectory_path = "trajectory_8x8_ppo.jsonl"
    
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
        device="cpu"
    )
    
    recorder = TrajectoryRecorderCallback(filename=trajectory_path)
    
    try:
        # 200,000 steps
        model.learn(total_timesteps=200_000, callback=recorder)
    finally:
        recorder.close()
        
    print("Finished PPO Experiment")

if __name__ == "__main__":
    run_experiment()
