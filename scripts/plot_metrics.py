import os

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import pandas as pd

# Configuration
jobs = [
  {"id": 56, "robots": 2, "label": "2 Robots"},
  {"id": 55, "robots": 3, "label": "3 Robots"},
  {"id": 57, "robots": 4, "label": "4 Robots"},
  {"id": 58, "robots": 5, "label": "5 Robots"},
]

ARTIFACT_DIR = "/home/hama/work/master/security-robot-be/report/result/cycle12"
CSV_DIR = "/home/hama/work/master/security-robot-be"


def plot_metric(metric_col, title, ylabel, filename, jobs_data, show_episodes=False):
  plt.figure(figsize=(10, 6))

  colors = plt.cm.tab10.colors  # Use default color cycle manually to match lines

  for i, job in enumerate(jobs_data):
    df = job["df"]
    color = colors[i % len(colors)]

    # Smoothing
    smoothed = df[metric_col].rolling(window=10, min_periods=1).mean()
    plt.plot(df["timestep"], smoothed, label=job["label"], linewidth=2, color=color)

    # Plot episode separators if requested
    if show_episodes:
      # Find indices where episode changes
      # df['episode'] is mono-increasing. Changes happen when diff > 0
      # We use the index to find the timestep
      episode_changes = df[df["episode"].diff() > 0]

      # Plot raw lines, but maybe too many. Plot only for the last job (5 robots) to avoid clutter?
      # Or plot for all? Let's plot for all with very low alpha
      for _, row in episode_changes.iterrows():
        plt.axvline(x=row["timestep"], color=color, alpha=0.15, linestyle=":", linewidth=1)

  # Title removed as requested
  # plt.title(title, fontsize=14)
  plt.xlabel("Timesteps", fontsize=12)
  plt.ylabel(ylabel, fontsize=12)
  plt.grid(True, linestyle="--", alpha=0.7)
  plt.legend(fontsize=10)

  # Format X axis with K (e.g. 10000 -> 10k)
  def k_formatter(x, pos):
    return f"{int(x / 1000)}k"

  plt.gca().xaxis.set_major_formatter(FuncFormatter(k_formatter))

  output_path = os.path.join(ARTIFACT_DIR, filename)
  plt.savefig(output_path, dpi=100)
  print(f"Saved {output_path}")
  plt.close()


def main():
  # Load Data
  jobs_data = []
  for job in jobs:
    csv_path = os.path.join(CSV_DIR, f"job_{job['id']}_metrics.csv")
    if not os.path.exists(csv_path):
      print(f"Warning: {csv_path} not found. Skipping.")
      continue

    try:
      df = pd.read_csv(csv_path)
      job["df"] = df
      jobs_data.append(job)
    except Exception as e:
      print(f"Error reading {csv_path}: {e}")

  if not jobs_data:
    print("No data loaded.")
    return

  # 1. Team Reward Comparison
  plot_metric(
    "estimated_team_reward",
    "Team Reward Comparison (Sum of Rewards)",
    "Team Reward",
    "chart_team_reward_comparison.png",
    jobs_data,
  )

  # 2. Coverage Comparison
  plot_metric(
    "coverage_ratio",
    "Coverage Ratio Comparison",
    "Coverage (0-1)",
    "chart_coverage_comparison.png",
    jobs_data,
  )

  # 3. Threat Level Comparison (with indicators)
  plot_metric(
    "threat_level_avg",
    "Average Threat Level Comparison",
    "Threat Level",
    "chart_threat_comparison.png",
    jobs_data,
    show_episodes=True,
  )

  # 4. Individual Mean Reward (to show the decline)
  plot_metric(
    "reward",
    "Mean Reward Per Robot (Standard Metric)",
    "Mean Reward",
    "chart_mean_reward_comparison.png",
    jobs_data,
  )


if __name__ == "__main__":
  main()
