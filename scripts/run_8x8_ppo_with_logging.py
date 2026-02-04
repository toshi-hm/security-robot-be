
import os
import sys
import gymnasium as gym
import numpy as np
import csv
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.logger import configure

# Add app to path
sys.path.append(os.getcwd())
try:
    from rl.environments.security_env import SecurityEnvironment
except ImportError:
    sys.path.append(os.path.join(os.getcwd(), ".."))
    from rl.environments.security_env import SecurityEnvironment

# Logging setup
LOG_DIR = "logs_8x8"
os.makedirs(LOG_DIR, exist_ok=True)

class CoverageMetricsCallback(BaseCallback):
    """
    Log 'Step to 100% Coverage' for each episode.
    """
    def __init__(self, filename: str, verbose: int = 0):
        super().__init__(verbose)
        self.filename = filename
        # Initialize CSV
        with open(self.filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['episode', 'steps_to_100', 'final_coverage'])
            
        self.episode_count = 1
        self.current_episode_start_step = 0
        self.reached_100 = False
        self.steps_to_100 = None

    def _on_step(self) -> bool:
        env = self.training_env.envs[0].unwrapped
        info = env._get_info()
        cov = info.get("coverage_ratio", 0.0)
        
        current_step_in_ep = self.num_timesteps - self.current_episode_start_step
        
        if cov >= 1.0 and not self.reached_100:
            self.reached_100 = True
            self.steps_to_100 = current_step_in_ep

        return True
        
    def _on_step_end(self, _locals, _globals) -> None:
        if 'dones' in _locals and _locals['dones'][0]:
            # Episode finished
            env = self.training_env.envs[0].unwrapped
            final_cov = env._get_info().get("coverage_ratio", 0.0)
            
            # If never reached 100%, use max steps (4000) or None?
            # User wants stats, let's use actual steps or 4000 if not reached
            if not self.reached_100:
                 # If coverage is 1.0 at very end
                 if final_cov >= 1.0:
                     self.steps_to_100 = 4000
                 else:
                     self.steps_to_100 = 4000 # Sentinel for "Failed to reach"
            
            with open(self.filename, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([self.episode_count, self.steps_to_100, final_cov])
            
            self.episode_count += 1
            self.reached_100 = False
            self.steps_to_100 = None
            self.current_episode_start_step = self.num_timesteps

def run_experiment():
    print("Starting 8x8 Single Agent PPO Experiment with Logging...")
    
    # 8x8 Config
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

    # Monitor Logs (Reward, Length, Threat, Coverage)
    env = SecurityEnvironment(**env_config)
    env = Monitor(env, filename=os.path.join(LOG_DIR, "monitor"), info_keywords=("coverage_ratio", "average_threat_level"))
    
    # SB3 Logger (Losses -> progress.csv)
    new_logger = configure(LOG_DIR, ["stdout", "csv"])
    
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
    model.set_logger(new_logger)
    
    # Custom Callback for coverage steps
    cov_callback = CoverageMetricsCallback(filename=os.path.join(LOG_DIR, "coverage_metrics.csv"))
    
    total_steps = 200_000
    model.learn(total_timesteps=total_steps, callback=cov_callback)
    
    print(f"Experiment Finished. Logs in {LOG_DIR}")

if __name__ == "__main__":
    run_experiment()
