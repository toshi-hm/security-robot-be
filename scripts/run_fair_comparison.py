"""
公平な比較実験スクリプト

PPOとテンプレートエージェントを同じ条件で比較:
- 1エピソードあたりの平均報酬で比較
- 同じエピソード数で評価
"""

import csv
from datetime import datetime
import logging
import os

import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from tqdm import tqdm

from rl.agents.template_agents import HorizontalScanAgent, SpiralAgent
from rl.environments.security_env import SecurityEnvironment

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOTAL_TIMESTEPS = 200_000  # Increased training steps
MAX_EPISODE_STEPS = 1000
NUM_EVAL_EPISODES = 10  # Number of episodes for evaluation
OUTPUT_DIR = "report/result/cycle12_fair_comparison"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def make_env(num_robots):
  def _init():
    return SecurityEnvironment(
      width=20,
      height=20,
      num_robots=num_robots,
      max_episode_steps=MAX_EPISODE_STEPS,
      exploration_bonus=1.0,
      revisit_penalty=0.05,
      revisit_window=50,
    )

  return _init


def evaluate_policy(model, num_robots, num_episodes=10):
  """Evaluate PPO policy over multiple episodes."""
  episode_rewards = []
  episode_coverages = []

  for _ in range(num_episodes):
    env = SecurityEnvironment(
      width=20,
      height=20,
      num_robots=num_robots,
      max_episode_steps=MAX_EPISODE_STEPS,
      exploration_bonus=1.0,
      revisit_penalty=0.05,
      revisit_window=50,
    )
    obs, _ = env.reset()
    total_reward = 0.0
    done = False
    steps = 0

    while not done and steps < MAX_EPISODE_STEPS:
      action, _ = model.predict(obs, deterministic=True)
      obs, reward, terminated, truncated, info = env.step(action)
      total_reward += reward
      steps += 1
      done = terminated or truncated

    episode_rewards.append(total_reward)
    episode_coverages.append(info.get("coverage_ratio", 0.0))

  return {
    "mean_reward": np.mean(episode_rewards),
    "std_reward": np.std(episode_rewards),
    "mean_coverage": np.mean(episode_coverages),
    "std_coverage": np.std(episode_coverages),
  }


def evaluate_template(AgentClass, num_robots, num_episodes=10):
  """Evaluate template agent over multiple episodes."""
  episode_rewards = []
  episode_coverages = []

  for ep in range(num_episodes):
    env = SecurityEnvironment(
      width=20,
      height=20,
      num_robots=num_robots,
      max_episode_steps=MAX_EPISODE_STEPS,
      exploration_bonus=1.0,
      revisit_penalty=0.05,
      revisit_window=50,
    )
    obs, _ = env.reset()

    # Create agents
    agents = [AgentClass(width=env.width, height=env.height) for _ in range(num_robots)]
    obstacle_set = {
      (x, y) for y in range(env.height) for x in range(env.width) if env.obstacles[y][x]
    }

    total_reward = 0.0
    done = False
    steps = 0

    while not done and steps < MAX_EPISODE_STEPS:
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

      obs, reward, terminated, truncated, info = env.step(actions)
      total_reward += reward
      steps += 1
      done = terminated or truncated

    episode_rewards.append(total_reward)
    episode_coverages.append(info.get("coverage_ratio", 0.0))

  return {
    "mean_reward": np.mean(episode_rewards),
    "std_reward": np.std(episode_rewards),
    "mean_coverage": np.mean(episode_coverages),
    "std_coverage": np.std(episode_coverages),
  }


def main():
  timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
  num_robots = 3

  # Train PPO
  logger.info(f"Training PPO with {TOTAL_TIMESTEPS} timesteps...")
  vec_env = DummyVecEnv([make_env(num_robots)])
  model = PPO(
    "MlpPolicy",
    vec_env,
    learning_rate=3e-4,
    n_steps=2048,
    batch_size=64,
    n_epochs=10,
    gamma=0.99,
    verbose=0,
    device="cpu",
  )

  # Training loop with progress
  with tqdm(total=TOTAL_TIMESTEPS, desc="PPO Training") as pbar:
    steps_trained = 0
    while steps_trained < TOTAL_TIMESTEPS:
      batch = min(10000, TOTAL_TIMESTEPS - steps_trained)
      model.learn(total_timesteps=batch, reset_num_timesteps=False)
      steps_trained += batch
      pbar.update(batch)

  # Evaluate all methods
  logger.info("Evaluating PPO...")
  ppo_results = evaluate_policy(model, num_robots, NUM_EVAL_EPISODES)

  logger.info("Evaluating Spiral...")
  spiral_results = evaluate_template(SpiralAgent, num_robots, NUM_EVAL_EPISODES)

  logger.info("Evaluating Zigzag...")
  zigzag_results = evaluate_template(HorizontalScanAgent, num_robots, NUM_EVAL_EPISODES)

  # Print results
  print("\n" + "=" * 70)
  print("FAIR COMPARISON RESULTS (Per-Episode Metrics)")
  print("=" * 70)
  print(f"\nTraining: {TOTAL_TIMESTEPS} timesteps, Evaluation: {NUM_EVAL_EPISODES} episodes")
  print()

  print(f"{'Method':<15} {'Reward (mean±std)':<25} {'Coverage (mean±std)':<20}")
  print("-" * 60)
  print(
    f"{'PPO':<15} {ppo_results['mean_reward']:>8.2f} ± {ppo_results['std_reward']:<8.2f} "
    f"{ppo_results['mean_coverage'] * 100:>6.2f}% ± {ppo_results['std_coverage'] * 100:<5.2f}%"
  )
  print(
    f"{'Spiral':<15} {spiral_results['mean_reward']:>8.2f} ± {spiral_results['std_reward']:<8.2f} "
    f"{spiral_results['mean_coverage'] * 100:>6.2f}% ± {spiral_results['std_coverage'] * 100:<5.2f}%"
  )
  print(
    f"{'Zigzag':<15} {zigzag_results['mean_reward']:>8.2f} ± {zigzag_results['std_reward']:<8.2f} "
    f"{zigzag_results['mean_coverage'] * 100:>6.2f}% ± {zigzag_results['std_coverage'] * 100:<5.2f}%"
  )

  # Save results
  results_file = f"{OUTPUT_DIR}/comparison_{timestamp}.csv"
  with open(results_file, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["method", "mean_reward", "std_reward", "mean_coverage", "std_coverage"])
    writer.writerow(
      [
        "PPO",
        ppo_results["mean_reward"],
        ppo_results["std_reward"],
        ppo_results["mean_coverage"],
        ppo_results["std_coverage"],
      ]
    )
    writer.writerow(
      [
        "Spiral",
        spiral_results["mean_reward"],
        spiral_results["std_reward"],
        spiral_results["mean_coverage"],
        spiral_results["std_coverage"],
      ]
    )
    writer.writerow(
      [
        "Zigzag",
        zigzag_results["mean_reward"],
        zigzag_results["std_reward"],
        zigzag_results["mean_coverage"],
        zigzag_results["std_coverage"],
      ]
    )

  print(f"\nResults saved to: {results_file}")

  # Determine winner
  print("\n" + "=" * 70)
  if ppo_results["mean_reward"] > max(spiral_results["mean_reward"], zigzag_results["mean_reward"]):
    print("WINNER: PPO (Reinforcement Learning)")
  else:
    print("WINNER: Template Agent (needs more training or tuning)")
  print("=" * 70)


if __name__ == "__main__":
  main()
