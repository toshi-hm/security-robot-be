"""
Cycle 12実験と Baseline実験を実行するスクリプト。

自動警備ロジック修正後の実験:
- Cycle 12: PPO + SecurityEnvironment (num_robots=3)
- Baseline: Template Agent (Spiral, Zigzag) での比較

使用方法:
  cd /home/hama/work/master/security-robot-be
  source .venv/bin/activate
  python scripts/run_cycle12_experiment.py
"""

import csv
from datetime import datetime
import logging
import os
import time

import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from tqdm import tqdm

from rl.agents.template_agents import (
  HorizontalScanAgent,
  RandomWalkAgent,
  SpiralAgent,
  VerticalScanAgent,
)
from rl.environments.security_env import SecurityEnvironment

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
TOTAL_TIMESTEPS = 100_000
MAX_EPISODE_STEPS = 1000
LOG_INTERVAL = 250
OUTPUT_DIR = "report/result/cycle12_autopatrol"


def make_env(num_robots: int):
  """環境を作成"""

  def _init():
    return SecurityEnvironment(
      width=20,
      height=20,
      num_robots=num_robots,
      max_episode_steps=MAX_EPISODE_STEPS,
      map_type="random",
    )

  return _init


def run_ppo_experiment(num_robots: int, output_file: str):
  """PPO訓練を実行"""
  logger.info(f"Starting PPO experiment with {num_robots} robots")

  # Create environment
  vec_env = DummyVecEnv([make_env(num_robots)])

  # Initialize PPO model
  model = PPO(
    "MlpPolicy",
    vec_env,
    learning_rate=3e-4,
    n_steps=2048,
    batch_size=64,
    n_epochs=10,
    gamma=0.99,
    verbose=0,
  )

  # Training with logging
  metrics = []
  episode_rewards = []
  episode_lengths = []

  total_steps = 0
  start_time = time.time()

  obs = vec_env.reset()
  current_episode_reward = 0.0
  current_episode_length = 0

  with tqdm(total=TOTAL_TIMESTEPS, desc=f"PPO {num_robots} robots") as pbar:
    while total_steps < TOTAL_TIMESTEPS:
      # Train for a batch
      batch_steps = min(LOG_INTERVAL, TOTAL_TIMESTEPS - total_steps)
      model.learn(total_timesteps=batch_steps, reset_num_timesteps=False)
      total_steps += batch_steps
      pbar.update(batch_steps)

      # Evaluate current policy
      eval_env = SecurityEnvironment(
        width=20, height=20, num_robots=num_robots, max_episode_steps=MAX_EPISODE_STEPS
      )
      eval_obs, _ = eval_env.reset()
      eval_reward = 0.0
      eval_steps = 0
      eval_done = False

      while not eval_done and eval_steps < MAX_EPISODE_STEPS:
        action, _ = model.predict(eval_obs, deterministic=True)
        eval_obs, reward, terminated, truncated, info = eval_env.step(action)
        eval_reward += reward
        eval_steps += 1
        eval_done = terminated or truncated

      # Log metrics
      elapsed_time = time.time() - start_time
      metrics.append(
        {
          "timestep": total_steps,
          "mean_reward": eval_reward,
          "episode_length": eval_steps,
          "coverage_ratio": info.get("coverage_ratio", 0.0),
          "average_threat_level": info.get("average_threat_level", 0.0),
          "average_battery": info.get("battery_percentage", 100.0),
          "elapsed_time": elapsed_time,
        }
      )

  # Save metrics to CSV
  os.makedirs(os.path.dirname(output_file), exist_ok=True)
  with open(output_file, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=metrics[0].keys())
    writer.writeheader()
    writer.writerows(metrics)

  logger.info(f"PPO experiment completed. Results saved to {output_file}")

  # Return final metrics
  return {
    "final_reward": metrics[-1]["mean_reward"],
    "final_coverage": metrics[-1]["coverage_ratio"],
    "final_threat": metrics[-1]["average_threat_level"],
  }


def run_baseline_experiment(num_robots: int, pattern: str, output_file: str):
  """Template Agentでのベースライン実験"""
  logger.info(f"Starting baseline ({pattern}) experiment with {num_robots} robots")

  # Get agent class
  agent_classes = {
    "spiral": SpiralAgent,
    "zigzag": HorizontalScanAgent,
    "vertical": VerticalScanAgent,
    "random": RandomWalkAgent,
  }
  AgentClass = agent_classes.get(pattern.lower())
  if AgentClass is None:
    raise ValueError(f"Unknown pattern: {pattern}")

  # Create environment and agents
  env = SecurityEnvironment(
    width=20, height=20, num_robots=num_robots, max_episode_steps=MAX_EPISODE_STEPS
  )

  # Note: Template agents expect (x, y) format for obstacles
  # Convert grid[y][x] to set of (x, y) tuples
  obstacle_set = {
    (x, y) for y in range(env.height) for x in range(env.width) if env.obstacles[y][x]
  }

  agents = [
    AgentClass(
      width=env.width,
      height=env.height,
    )
    for i in range(num_robots)
  ]

  # Run simulation
  metrics = []
  total_steps = 0
  episode_count = 0
  start_time = time.time()
  cumulative_reward = 0.0

  obs, _ = env.reset()

  with tqdm(total=TOTAL_TIMESTEPS, desc=f"Baseline {pattern} {num_robots} robots") as pbar:
    while total_steps < TOTAL_TIMESTEPS:
      # Get actions from all agents
      actions = np.array(
        [
          agent.get_action(
            robot_x=env.robot_positions[i][0],
            robot_y=env.robot_positions[i][1],
            robot_direction=env.robot_directions[i],
            obstacles=obstacle_set,
          )
          for i, agent in enumerate(agents)
        ]
      )

      # Step environment
      obs, reward, terminated, truncated, info = env.step(actions)
      cumulative_reward += reward
      total_steps += 1
      pbar.update(1)

      # Log at interval
      if total_steps % LOG_INTERVAL == 0:
        elapsed_time = time.time() - start_time
        metrics.append(
          {
            "timestep": total_steps,
            "mean_reward": cumulative_reward / (episode_count + 1)
            if episode_count > 0
            else cumulative_reward,
            "episode_length": total_steps % MAX_EPISODE_STEPS,
            "coverage_ratio": info.get("coverage_ratio", 0.0),
            "average_threat_level": info.get("average_threat_level", 0.0),
            "average_battery": info.get("battery_percentage", 100.0),
            "elapsed_time": elapsed_time,
          }
        )

      if terminated or truncated:
        episode_count += 1
        obs, _ = env.reset()
        # Update obstacle set after reset
        obstacle_set = {
          (x, y) for y in range(env.height) for x in range(env.width) if env.obstacles[y][x]
        }
        for agent in agents:
          agent.reset()

  # Save metrics
  os.makedirs(os.path.dirname(output_file), exist_ok=True)
  with open(output_file, "w", newline="") as f:
    if metrics:
      writer = csv.DictWriter(f, fieldnames=metrics[0].keys())
      writer.writeheader()
      writer.writerows(metrics)

  logger.info(f"Baseline experiment completed. Results saved to {output_file}")

  return {
    "final_reward": metrics[-1]["mean_reward"] if metrics else 0.0,
    "final_coverage": metrics[-1]["coverage_ratio"] if metrics else 0.0,
    "final_threat": metrics[-1]["average_threat_level"] if metrics else 0.0,
  }


def main():
  """メイン実行"""
  os.makedirs(OUTPUT_DIR, exist_ok=True)

  timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

  results = {}

  # PPO experiments (Cycle 12)
  for num_robots in [3]:  # まずは3ロボットで実験
    output_file = f"{OUTPUT_DIR}/ppo_{num_robots}_robots_{timestamp}.csv"
    result = run_ppo_experiment(num_robots, output_file)
    results[f"ppo_{num_robots}"] = result

  # Baseline experiments
  for pattern in ["spiral", "zigzag"]:
    for num_robots in [3]:
      output_file = f"{OUTPUT_DIR}/baseline_{pattern}_{num_robots}_{timestamp}.csv"
      result = run_baseline_experiment(num_robots, pattern, output_file)
      results[f"baseline_{pattern}_{num_robots}"] = result

  # Print summary
  print("\n" + "=" * 60)
  print("Experiment Summary")
  print("=" * 60)
  for name, result in results.items():
    print(f"\n{name}:")
    print(f"  Final Reward: {result['final_reward']:.2f}")
    print(f"  Coverage: {result['final_coverage']:.2%}")
    print(f"  Avg Threat: {result['final_threat']:.4f}")

  # Save summary
  summary_file = f"{OUTPUT_DIR}/summary_{timestamp}.txt"
  with open(summary_file, "w") as f:
    f.write("Cycle 12 Experiment Summary (Automatic Patrol)\n")
    f.write("=" * 60 + "\n\n")
    for name, result in results.items():
      f.write(f"{name}:\n")
      f.write(f"  Final Reward: {result['final_reward']:.2f}\n")
      f.write(f"  Coverage: {result['final_coverage']:.2%}\n")
      f.write(f"  Avg Threat: {result['final_threat']:.4f}\n\n")

  print(f"\nSummary saved to {summary_file}")


if __name__ == "__main__":
  main()
