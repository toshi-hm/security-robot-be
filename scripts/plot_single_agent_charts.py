"""
Generate single-agent experiment charts from Job 75 metrics.
Creates: coverage curve, threat trend, threat transition, and PPO loss charts.
"""

import json
import os
import subprocess

import matplotlib.pyplot as plt
import numpy as np

OUTPUT_DIR = "/home/hama/work/master/masterpj-tex/Figures"
SESSION_ID = 77


def fetch_metrics(session_id: int) -> list:
  """Fetch all metrics from API."""
  all_metrics = []
  for page in range(1, 10):  # Fetch up to 9 pages
    cmd = f'curl -s "http://localhost:8000/api/v1/training/sessions/{session_id}/metrics?page={page}&page_size=500"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    try:
      data = json.loads(result.stdout)
      metrics = data.get("metrics", [])
      if not metrics:
        break
      all_metrics.extend(metrics)
    except:
      break
  return all_metrics


def plot_coverage_curve(metrics: list):
  """Plot coverage rate over episodes."""
  # Get final coverage per episode
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

  plt.figure(figsize=(8, 5), dpi=150)
  plt.plot(eps, coverage, "g-", alpha=0.5, linewidth=1, label="Coverage")
  plt.plot(ma_eps, ma, "orange", linewidth=2, label="5-episode MA")
  plt.xlabel("Episode", fontsize=11)
  plt.ylabel("Coverage Rate", fontsize=11)
  plt.xlim(left=1)  # Align x-axis to episode 1
  plt.grid(True, linestyle="--", alpha=0.6)
  plt.legend()
  plt.tight_layout()
  plt.savefig(f"{OUTPUT_DIR}/single_agent_coverage_curve.png", facecolor="white")
  plt.close()
  print(f"Saved: {OUTPUT_DIR}/single_agent_coverage_curve.png")

  # Return final stats
  final_10 = coverage[-10:]
  return np.mean(final_10), np.std(final_10)


def plot_threat_trend(metrics: list):
  """Plot average threat level trend over episodes."""
  episodes = {}
  for m in metrics:
    ep = m.get("episode", 0)
    if ep > 0:
      if ep not in episodes or m.get("timestep", 0) > episodes[ep].get("timestep", 0):
        episodes[ep] = m

  eps = sorted(episodes.keys())
  threats = [episodes[e].get("threat_level_avg", 0) for e in eps]

  # Moving average
  window = 5
  ma = np.convolve(threats, np.ones(window) / window, mode="valid")
  ma_eps = eps[window - 1 :]

  # Linear regression
  x = np.array(eps)
  y = np.array(threats)
  slope, intercept = np.polyfit(x, y, 1)
  regression_line = slope * x + intercept

  plt.figure(figsize=(8, 5), dpi=150)
  plt.scatter(eps, threats, c="lightblue", s=30, alpha=0.7, label="Threat Level")
  plt.plot(ma_eps, ma, "r-", linewidth=2, label="5-episode MA")
  plt.plot(eps, regression_line, "b--", linewidth=1.5, label=f"Regression (slope={slope:.4f})")
  plt.xlabel("Episode", fontsize=11)
  plt.ylabel("Average Threat Level", fontsize=11)
  plt.xlim(left=1)  # Align x-axis to episode 1
  plt.grid(True, linestyle="--", alpha=0.6)
  plt.legend()
  plt.tight_layout()
  plt.savefig(f"{OUTPUT_DIR}/single_agent_threat_trend.png", facecolor="white")
  plt.close()
  print(f"Saved: {OUTPUT_DIR}/single_agent_threat_trend.png")

  return slope, threats[0] if threats else 0, threats[-1] if threats else 0


def plot_threat_transition(metrics: list, target_episode: int = None):
  """Plot threat transition within a single episode."""
  # Find episode with highest coverage
  episodes = {}
  for m in metrics:
    ep = m.get("episode", 0)
    if ep > 0:
      if ep not in episodes:
        episodes[ep] = []
      episodes[ep].append(m)

  if target_episode is None:
    # Find best episode
    best_ep = max(
      episodes.keys(), key=lambda e: max(m.get("coverage_ratio", 0) for m in episodes[e])
    )
    target_episode = best_ep

  ep_metrics = sorted(episodes.get(target_episode, []), key=lambda x: x.get("timestep", 0))
  steps = list(range(len(ep_metrics)))
  threats = [m.get("threat_level_avg", 0) for m in ep_metrics]

  plt.figure(figsize=(8, 5), dpi=150)
  plt.plot(steps, threats, "b-", linewidth=1.5)
  plt.xlabel("Step", fontsize=11)
  plt.ylabel("Average Threat Level", fontsize=11)
  plt.xlim(left=1)  # Align x-axis to episode 1
  plt.grid(True, linestyle="--", alpha=0.6)
  plt.tight_layout()
  plt.savefig(f"{OUTPUT_DIR}/single_agent_threat_transition.png", facecolor="white")
  plt.close()
  print(f"Saved: {OUTPUT_DIR}/single_agent_threat_transition.png (episode {target_episode})")

  # Get coverage for this episode
  max_cov = max(m.get("coverage_ratio", 0) for m in ep_metrics)
  return target_episode, max_cov


def plot_ppo_loss(metrics: list):
  """Plot PPO loss metrics over timesteps."""
  # Sort by timestep
  sorted_metrics = sorted(metrics, key=lambda x: x.get("timestep", 0))

  timesteps = []
  approx_kl = []
  clip_fraction = []
  policy_loss = []
  value_loss = []

  for m in sorted_metrics:
    ts = m.get("timestep", 0)

    # Try to find metrics in additional_metrics first, then root level
    add_metrics = m.get("additional_metrics") or {}

    kl = add_metrics.get("approx_kl")
    if kl is None:
      kl = m.get("approx_kl")

    clip = add_metrics.get("clip_fraction")
    if clip is None:
      clip = m.get("clip_fraction")

    pol = add_metrics.get("policy_gradient_loss")
    if pol is None:
      pol = m.get("policy_gradient_loss")

    val = add_metrics.get("value_loss")
    if val is None:
      val = m.get("value_loss")

    # Only add if we have at least one metric
    if kl is not None or clip is not None or pol is not None or val is not None:
      timesteps.append(ts)
      approx_kl.append(kl if kl is not None else 0)
      clip_fraction.append(clip if clip is not None else 0)
      policy_loss.append(pol if pol is not None else 0)
      value_loss.append(val if val is not None else 0)

  fig, axes = plt.subplots(2, 2, figsize=(10, 8), dpi=150)

  # (a) Approx KL
  ax = axes[0, 0]
  ax.plot(timesteps, approx_kl, "b-", linewidth=0.8)
  ax.set_xlabel("Timesteps")
  ax.set_ylabel("Approx KL")
  ax.set_title("(a) Approx KL Divergence")
  ax.set_xlim(left=0)  # Align x-axis to 0
  ax.grid(True, linestyle="--", alpha=0.6)

  # (b) Clip Fraction
  ax = axes[0, 1]
  ax.plot(timesteps, clip_fraction, "orange", linewidth=0.8)
  ax.set_xlabel("Timesteps")
  ax.set_ylabel("Clip Fraction")
  ax.set_title("(b) Clip Fraction")
  ax.set_xlim(left=0)  # Align x-axis to 0
  ax.grid(True, linestyle="--", alpha=0.6)

  # (c) Policy Loss
  ax = axes[1, 0]
  ax.plot(timesteps, policy_loss, "g-", linewidth=0.8)
  ax.set_xlabel("Timesteps")
  ax.set_ylabel("Policy Loss")
  ax.set_title("(c) Policy Gradient Loss")
  ax.set_xlim(left=0)  # Align x-axis to 0
  ax.grid(True, linestyle="--", alpha=0.6)

  # (d) Value Loss
  ax = axes[1, 1]
  ax.plot(timesteps, value_loss, "r-", linewidth=0.8)
  ax.set_xlabel("Timesteps")
  ax.set_ylabel("Value Loss")
  ax.set_title("(d) Value Loss")
  ax.set_xlim(left=0)  # Align x-axis to 0
  ax.grid(True, linestyle="--", alpha=0.6)

  plt.tight_layout()
  plt.savefig(f"{OUTPUT_DIR}/single_agent_ppo_loss.png", facecolor="white")
  plt.close()
  print(f"Saved: {OUTPUT_DIR}/single_agent_ppo_loss.png")

  # Return stats
  return {
    "approx_kl_mean": np.mean([x for x in approx_kl if x]),
    "approx_kl_std": np.std([x for x in approx_kl if x]),
    "clip_fraction_mean": np.mean([x for x in clip_fraction if x]),
    "clip_fraction_std": np.std([x for x in clip_fraction if x]),
  }


def plot_reward_curve(metrics: list):
  """Plot cumulative reward over episodes."""
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

  plt.figure(figsize=(8, 5), dpi=150)
  plt.plot(eps, rewards, "c-", alpha=0.5, linewidth=1, label="Reward")
  plt.plot(ma_eps, ma, "b-", linewidth=2, label="5-episode MA")
  plt.xlabel("Episode", fontsize=11)
  plt.ylabel("Cumulative Reward", fontsize=11)
  plt.xlim(left=1)  # Align x-axis to episode 1
  plt.grid(True, linestyle="--", alpha=0.6)
  plt.legend()
  plt.tight_layout()
  plt.savefig(f"{OUTPUT_DIR}/single_agent_reward_curve.png", facecolor="white")
  plt.close()
  print(f"Saved: {OUTPUT_DIR}/single_agent_reward_curve.png")

  return np.mean(rewards[-10:]), np.std(rewards[-10:])


def main():
  os.makedirs(OUTPUT_DIR, exist_ok=True)

  print(f"Fetching metrics for Session {SESSION_ID}...")
  metrics = fetch_metrics(SESSION_ID)
  print(f"Fetched {len(metrics)} metric records")

  if not metrics:
    print("No metrics found!")
    return

  # Generate charts
  print("\nGenerating charts...")

  rew_mean, rew_std = plot_reward_curve(metrics)
  print(f"  Final reward: {rew_mean:.2f} ± {rew_std:.2f}")

  cov_mean, cov_std = plot_coverage_curve(metrics)
  print(f"  Final coverage: {cov_mean:.3f} ± {cov_std:.3f}")

  slope, init_threat, final_threat = plot_threat_trend(metrics)
  print(f"  Threat trend slope: {slope:.4f}")
  print(f"  Initial threat: {init_threat:.3f}, Final: {final_threat:.3f}")

  best_ep, best_cov = plot_threat_transition(metrics, target_episode=47)
  print(f"  Best episode: {best_ep} with coverage {best_cov:.3f}")

  ppo_stats = plot_ppo_loss(metrics)
  print(f"  Approx KL: {ppo_stats['approx_kl_mean']:.4f} ± {ppo_stats['approx_kl_std']:.4f}")
  print(
    f"  Clip fraction: {ppo_stats['clip_fraction_mean']:.3f} ± {ppo_stats['clip_fraction_std']:.3f}"
  )


if __name__ == "__main__":
  main()
