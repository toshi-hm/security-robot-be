import numpy as np
import pandas as pd

from rl.environments.enhanced_env import EnhancedSecurityEnvironment


def run_experiment(
  num_robots_list: list[int] | None = None, episodes: int = 5, steps: int = 100
) -> None:
  if num_robots_list is None:
    num_robots_list = [1, 3, 5]

  results = []

  print("Running Reward Scaling Analysis...")
  print(f"Episodes per config: {episodes}")
  print(f"Steps per episode: {steps}")
  print("-" * 60)
  for n_robots in num_robots_list:
    print(f"Running experiment with {n_robots} robots...")
    env = EnhancedSecurityEnvironment(width=10, height=10, num_robots=n_robots, render_mode=None)

    total_rewards: list[float] = []

    for _ in range(episodes):
      env.reset()
      ep_total: float = 0.0

      for _ in range(steps):
        # Simple random action for each robot
        actions = env.action_space.sample()

        _, reward, _, _, _ = env.step(actions)

        # In EnhancedSecurityEnvironment, step() returns the final combined reward.
        # We need to peek into the environment to see the components if we want detailed
        # breakdown. However, for this high-level check, we can look at the total reward
        # magnitude. To get components, we might need to instrument the env or just infer
        # from total. Actually, let's just track the total reward for now as a proxy for
        # "incentive magnitude".

        ep_total += float(reward)

      total_rewards.append(ep_total)

    avg_total = np.mean(total_rewards)
    std_total = np.std(total_rewards)

    print(f"  Avg Total Reward: {avg_total:.2f} (+/- {std_total:.2f})")
    print(f"  Avg Reward per Step: {avg_total / steps:.4f}")
    results.append(
      {
        "num_robots": n_robots,
        "avg_total_reward": avg_total,
        "avg_reward_per_step": avg_total / steps,
      }
    )

  print("-" * 60)
  print("Summary:")
  df = pd.DataFrame(results)
  print(df)

  # Analysis
  base_reward = df[df["num_robots"] == 1]["avg_total_reward"].values[0]
  print("\nScaling Analysis (Relative to 1 Robot):")
  for _, row in df.iterrows():
    ratio = row["avg_total_reward"] / base_reward
    print(f"  {int(row['num_robots'])} Robots: {ratio:.2f}x")


if __name__ == "__main__":
  run_experiment()
