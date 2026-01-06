"""
Generate multi-agent experiment charts from Jobs 72, 73, 74 metrics.
Creates: reward curve, coverage curve, threat trend, and PPO loss charts.
Each chart shows multiple robot counts (2, 3, 4) as separate lines.
"""

import matplotlib.pyplot as plt
import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

OUTPUT_DIR = "/home/hama/work/master/masterpj-tex/Figures"
DATABASE_URL = "postgresql+psycopg://security_robot:change_me@localhost:5432/security_robot"

# Multi-agent job IDs
JOBS = {
  2: 72,  # 2 robots
  3: 73,  # 3 robots
  4: 74,  # 4 robots
}

# Colors for each robot count
COLORS = {
  2: "blue",
  3: "green",
  4: "red",
}

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def fetch_metrics(job_id: int):
  """Fetch all metrics from database."""
  with Session() as db:
    query = text("""
            SELECT episode, timestep, reward, coverage_ratio, threat_level_avg, additional_metrics
            FROM trainingmetric
            WHERE job_id = :job_id
            ORDER BY timestep ASC
        """)
    result = db.execute(query, {"job_id": job_id}).fetchall()

    metrics = []
    for r in result:
      m = {
        "episode": r[0],
        "timestep": r[1],
        "reward": r[2],
        "coverage_ratio": r[3],
        "threat_level_avg": r[4],
      }
      # Parse additional_metrics if available
      if r[5]:
        add = r[5]
        if isinstance(add, dict):
          m["approx_kl"] = add.get("approx_kl")
          m["clip_fraction"] = add.get("clip_fraction")
          m["policy_gradient_loss"] = add.get("policy_gradient_loss")
          m["value_loss"] = add.get("value_loss")
      metrics.append(m)
    return metrics


def plot_reward_curve(all_metrics: dict):
  """Plot cumulative reward over episodes for all robot counts."""
  plt.figure(figsize=(10, 6), dpi=150)

  for num_robots, metrics in all_metrics.items():
    episodes = {}
    for m in metrics:
      ep = m.get("episode", 0)
      if ep > 0:
        if ep not in episodes or m.get("timestep", 0) > episodes[ep].get("timestep", 0):
          episodes[ep] = m

    eps = sorted(episodes.keys())
    rewards = [episodes[e].get("reward", 0) for e in eps]

    # Moving average
    window = 5
    ma = np.convolve(rewards, np.ones(window) / window, mode="valid")
    ma_eps = eps[window - 1 :]

    plt.plot(ma_eps, ma, color=COLORS[num_robots], linewidth=2, label=f"{num_robots} robots")

  plt.xlabel("Episode", fontsize=11)
  plt.ylabel("Cumulative Reward", fontsize=11)
  plt.xlim(left=1)
  plt.grid(True, linestyle="--", alpha=0.6)
  plt.legend()
  plt.tight_layout()
  plt.savefig(f"{OUTPUT_DIR}/multi_agent_reward_curve.png", facecolor="white")
  plt.close()
  print(f"Saved: {OUTPUT_DIR}/multi_agent_reward_curve.png")


def plot_coverage_curve(all_metrics: dict):
  """Plot coverage rate over episodes for all robot counts."""
  plt.figure(figsize=(10, 6), dpi=150)

  for num_robots, metrics in all_metrics.items():
    episodes = {}
    for m in metrics:
      ep = m.get("episode", 0)
      if ep > 0:
        if ep not in episodes or m.get("timestep", 0) > episodes[ep].get("timestep", 0):
          episodes[ep] = m

    eps = sorted(episodes.keys())
    coverage = [episodes[e].get("coverage_ratio", 0) for e in eps]

    # Moving average
    window = 5
    ma = np.convolve(coverage, np.ones(window) / window, mode="valid")
    ma_eps = eps[window - 1 :]

    plt.plot(ma_eps, ma, color=COLORS[num_robots], linewidth=2, label=f"{num_robots} robots")

  plt.xlabel("Episode", fontsize=11)
  plt.ylabel("Coverage Rate", fontsize=11)
  plt.xlim(left=1)
  plt.grid(True, linestyle="--", alpha=0.6)
  plt.legend()
  plt.tight_layout()
  plt.savefig(f"{OUTPUT_DIR}/multi_agent_coverage_curve.png", facecolor="white")
  plt.close()
  print(f"Saved: {OUTPUT_DIR}/multi_agent_coverage_curve.png")


def plot_threat_trend(all_metrics: dict):
  """Plot average threat level trend over episodes for all robot counts."""
  plt.figure(figsize=(10, 6), dpi=150)

  for num_robots, metrics in all_metrics.items():
    episodes = {}
    for m in metrics:
      ep = m.get("episode", 0)
      if ep > 0:
        threat = m.get("threat_level_avg", 0)
        if ep not in episodes:
          episodes[ep] = []
        episodes[ep].append(threat)

    eps = sorted(episodes.keys())
    avg_threats = [np.mean(episodes[e]) for e in eps]

    # Moving average
    window = 5
    ma = np.convolve(avg_threats, np.ones(window) / window, mode="valid")
    ma_eps = eps[window - 1 :]

    plt.plot(ma_eps, ma, color=COLORS[num_robots], linewidth=2, label=f"{num_robots} robots")

  plt.xlabel("Episode", fontsize=11)
  plt.ylabel("Average Threat Level", fontsize=11)
  plt.xlim(left=1)
  plt.grid(True, linestyle="--", alpha=0.6)
  plt.legend()
  plt.tight_layout()
  plt.savefig(f"{OUTPUT_DIR}/multi_agent_threat_trend.png", facecolor="white")
  plt.close()
  print(f"Saved: {OUTPUT_DIR}/multi_agent_threat_trend.png")


def plot_ppo_loss(all_metrics: dict):
  """Plot PPO loss metrics over timesteps for all robot counts."""
  fig, axes = plt.subplots(2, 2, figsize=(12, 10), dpi=150)

  for num_robots, metrics in all_metrics.items():
    sorted_metrics = sorted(metrics, key=lambda x: x.get("timestep", 0))

    timesteps = []
    approx_kl = []
    clip_fraction = []
    policy_loss = []
    value_loss = []

    for m in sorted_metrics:
      ts = m.get("timestep", 0)
      add_metrics = m.get("additional_metrics") or {}

      kl = add_metrics.get("approx_kl") or m.get("approx_kl")
      clip = add_metrics.get("clip_fraction") or m.get("clip_fraction")
      pol = add_metrics.get("policy_gradient_loss") or m.get("policy_gradient_loss")
      val = add_metrics.get("value_loss") or m.get("value_loss")

      if kl is not None or clip is not None or pol is not None or val is not None:
        timesteps.append(ts)
        approx_kl.append(kl if kl is not None else 0)
        clip_fraction.append(clip if clip is not None else 0)
        policy_loss.append(pol if pol is not None else 0)
        value_loss.append(val if val is not None else 0)

    color = COLORS[num_robots]
    label = f"{num_robots} robots"

    # (a) Approx KL
    axes[0, 0].plot(timesteps, approx_kl, color=color, linewidth=0.8, alpha=0.7, label=label)

    # (b) Clip Fraction
    axes[0, 1].plot(timesteps, clip_fraction, color=color, linewidth=0.8, alpha=0.7, label=label)

    # (c) Policy Loss
    axes[1, 0].plot(timesteps, policy_loss, color=color, linewidth=0.8, alpha=0.7, label=label)

    # (d) Value Loss
    axes[1, 1].plot(timesteps, value_loss, color=color, linewidth=0.8, alpha=0.7, label=label)

  # Configure subplots
  axes[0, 0].set_xlabel("Timesteps")
  axes[0, 0].set_ylabel("Approx KL")
  axes[0, 0].set_title("(a) Approx KL Divergence")
  axes[0, 0].set_xlim(left=0)
  axes[0, 0].grid(True, linestyle="--", alpha=0.6)
  axes[0, 0].legend()

  axes[0, 1].set_xlabel("Timesteps")
  axes[0, 1].set_ylabel("Clip Fraction")
  axes[0, 1].set_title("(b) Clip Fraction")
  axes[0, 1].set_xlim(left=0)
  axes[0, 1].grid(True, linestyle="--", alpha=0.6)
  axes[0, 1].legend()

  axes[1, 0].set_xlabel("Timesteps")
  axes[1, 0].set_ylabel("Policy Loss")
  axes[1, 0].set_title("(c) Policy Gradient Loss")
  axes[1, 0].set_xlim(left=0)
  axes[1, 0].grid(True, linestyle="--", alpha=0.6)
  axes[1, 0].legend()

  axes[1, 1].set_xlabel("Timesteps")
  axes[1, 1].set_ylabel("Value Loss")
  axes[1, 1].set_title("(d) Value Loss")
  axes[1, 1].set_xlim(left=0)
  axes[1, 1].grid(True, linestyle="--", alpha=0.6)
  axes[1, 1].legend()

  plt.tight_layout()
  plt.savefig(f"{OUTPUT_DIR}/multi_agent_ppo_loss.png", facecolor="white")
  plt.close()
  print(f"Saved: {OUTPUT_DIR}/multi_agent_ppo_loss.png")


def main():
  all_metrics = {}

  for num_robots, job_id in JOBS.items():
    print(f"Fetching metrics for Job {job_id} ({num_robots} robots)...")
    metrics = fetch_metrics(job_id)
    all_metrics[num_robots] = metrics
    print(f"  Fetched {len(metrics)} records")

  print("\nGenerating charts...")
  plot_reward_curve(all_metrics)
  plot_coverage_curve(all_metrics)
  plot_threat_trend(all_metrics)
  plot_ppo_loss(all_metrics)
  print("\nDone!")


if __name__ == "__main__":
  main()
