
import gymnasium as gym
import numpy as np
import json
import os
import sys
from stable_baselines3 import PPO
from stable_baselines3.common.monitor import Monitor

# Add app to path
sys.path.append(os.getcwd())
from rl.environments.security_env import SecurityEnvironment

def train_and_eval_ppo():
    print("=== Starting PPO Training (N=1) ===")
    
    # Thesis Configuration for Training
    env_config = {
        "width": 20,
        "height": 20,
        "num_robots": 1,
        "revisit_window": 100,
        "revisit_penalty": 0.05,
        "exploration_bonus": 1.0,
        "max_episode_steps": 4000,
        "reward_normalization_mode": "mean"
    }
    
    # Train
    env = SecurityEnvironment(**env_config)
    env = Monitor(env)
    
    # model = PPO(
    #     "MlpPolicy", 
    #     env, 
    #     verbose=1,
    #     learning_rate=0.0003,
    #     n_steps=2048,
    #     batch_size=64,
    #     gamma=0.99,
    #     gae_lambda=0.95,
    #     clip_range=0.2,
    #     n_epochs=10,
    #     device="cpu"
    # )
    
    # # Train for 200k steps (approx matches thesis)
    # model.learn(total_timesteps=200_000)
    # model.save("ppo_n1_final")
    # print("=== Training Complete & Model Saved ===")
    
    # Load trained model
    if os.path.exists("ppo_n1_final.zip"):
        model = PPO.load("ppo_n1_final", device="cpu")
        print("=== Loaded Saved Model ppo_n1_final ===")
    else:
        print("Model not found, cannot evaluate.")
        return
    
    # --- Evaluation Phase ---
    print("=== Starting Evaluation (50 Episodes) ===")
    
    eval_env = SecurityEnvironment(**env_config)
    # Don't wrap via Monitor here, just direct access for recording
    
    trajectory_file = "trajectory_ppo_eval_50.jsonl"
    
    with open(trajectory_file, "w") as f:
        for ep in range(1, 51):
            obs, _ = eval_env.reset()
            done = False
            step_count = 0
            
            # Record initial state
            _record_step(f, eval_env, step_count, ep)
            
            while not done:
                action, _ = model.predict(obs, deterministic=True)
                obs, reward, terminated, truncated, info = eval_env.step(action)
                done = terminated or truncated
                step_count += 1
                
                # Record step
                _record_step(f, eval_env, step_count, ep)
            
            print(f"Eval Episode {ep}/50: Steps={step_count}, Coverage={info.get('coverage_ratio', 0)}")

    print(f"=== Evaluation Complete. Trajectories saved to {trajectory_file} ===")

def _record_step(file_handle, env, step, episode):
    state = {
        "step": step,
        "episode": episode,
        "robot_x": env.robot_x,
        "robot_y": env.robot_y,
        "robot_positions": env.robot_positions, 
        # Convert bool numpy array to nested list for JSON serialization if needed
        # But obstacles is usually static list of bools?
        # env.obstacles is a 2D boolean array. serialization handles lists.
        "obstacles": env.obstacles,
        "coverage_ratio": env._get_info().get("coverage_ratio", 0.0),
        "threat_levels": env.threat_levels,
        "battery_levels": env.battery_levels,
        "robot_directions": env.robot_directions
    }
    # Handle numpy types
    class NumpyEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.floating):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            return super(NumpyEncoder, self).default(obj)
            
    file_handle.write(json.dumps(state, cls=NumpyEncoder) + "\n")

if __name__ == "__main__":
    train_and_eval_ppo()
