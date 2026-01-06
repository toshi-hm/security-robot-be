"""
Multi-agent trajectory visualization using exported JSON data from database.
Creates trajectory plots for 2, 3, and 4 robot configurations
at different training stages (early, mid, late episodes).
"""

import json
import os

import matplotlib.patches as patches
import matplotlib.pyplot as plt

# Configuration - using latest multi-agent experiments (Jobs 72-74)
SESSIONS = {
  2: 72,  # multi-agent-2robots
  3: 73,  # multi-agent-3robots
  4: 74,  # multi-agent-4robots
}

# Episodes to visualize
EPISODE_STAGES = [
  (1, "ep 1"),
  (2, "ep 2"),
  (25, "ep 25"),
  (49, "ep 49"),
  (50, "ep 50"),
]

OUTPUT_DIR = "/home/hama/work/master/masterpj-tex/Figures"
DATA_DIR = "/tmp/trajectories"

# Robot colors
COLORS = ["#e41a1c", "#377eb8", "#4daf4a", "#984ea3"]


def load_frames_from_json(session_id: int, episode: int) -> list:
  """Load playback frames from exported JSON file."""
  json_path = f"{DATA_DIR}/session{session_id}_ep{episode}.json"
  try:
    with open(json_path) as f:
      content = f.read().strip()
      if content:
        return json.loads(content)
  except Exception as e:
    print(f"Error loading {json_path}: {e}")
  return []


def extract_trajectories(frames: list, num_robots: int) -> tuple:
  """Extract robot trajectories and obstacles from frames."""
  trajectories = [[] for _ in range(num_robots)]
  obstacles = set()

  for frame in frames:
    # Extract robot positions
    robots = frame.get("robots", [])
    for i, robot in enumerate(robots[:num_robots]):
      if isinstance(robot, dict):
        x, y = robot.get("x", 0), robot.get("y", 0)
        trajectories[i].append((x, y))

    # Extract obstacles (from first frame only)
    if not obstacles:
      obs_data = frame.get("obstacles", {})
      if isinstance(obs_data, dict):
        obs_grid = obs_data.get("levels", [])
        for y_idx, row in enumerate(obs_grid):
          for x_idx, is_obstacle in enumerate(row):
            if is_obstacle:
              obstacles.add((x_idx, y_idx))

  return trajectories, obstacles


def plot_trajectory(ax, trajectories: list, obstacles: set, title: str, grid_size: int = 20):
  """Plot robot trajectories on a grid."""
  # Set up grid
  ax.set_xlim(-0.5, grid_size - 0.5)
  ax.set_ylim(-0.5, grid_size - 0.5)
  ax.set_aspect("equal")
  ax.invert_yaxis()

  # Draw grid lines (light)
  for i in range(grid_size + 1):
    ax.axhline(y=i - 0.5, color="#e0e0e0", linewidth=0.3)
    ax.axvline(x=i - 0.5, color="#e0e0e0", linewidth=0.3)

  # Draw obstacles
  for x, y in obstacles:
    rect = patches.Rectangle((x - 0.5, y - 0.5), 1, 1, linewidth=0, facecolor="#404040")
    ax.add_patch(rect)

  # Draw trajectories
  for i, traj in enumerate(trajectories):
    if len(traj) < 2:
      continue

    # Use every Nth point to avoid too dense lines
    step = max(1, len(traj) // 150)
    traj_sampled = traj[::step]

    # Color gradient: darker at start, lighter at end
    n_points = len(traj_sampled)
    for j in range(n_points - 1):
      alpha = 0.3 + 0.7 * (j / n_points)
      ax.plot(
        [traj_sampled[j][0], traj_sampled[j + 1][0]],
        [traj_sampled[j][1], traj_sampled[j + 1][1]],
        color=COLORS[i],
        alpha=alpha,
        linewidth=1.2,
      )

    # Mark start (circle) and end (square) positions
    if traj:
      ax.scatter(
        traj[0][0],
        traj[0][1],
        color=COLORS[i],
        s=50,
        marker="o",
        edgecolors="white",
        linewidths=1,
        zorder=10,
      )
      ax.scatter(
        traj[-1][0],
        traj[-1][1],
        color=COLORS[i],
        s=50,
        marker="s",
        edgecolors="white",
        linewidths=1,
        zorder=10,
      )

  ax.set_title(title, fontsize=9)
  ax.set_xticks([])
  ax.set_yticks([])


def generate_trajectory_figures():
  """Generate trajectory visualization figures using JSON data."""
  os.makedirs(OUTPUT_DIR, exist_ok=True)

  robot_counts = [2, 3, 4]

  # Create combined figure (3 robot counts × 5 stages) - horizontal layout
  fig, axes = plt.subplots(len(robot_counts), len(EPISODE_STAGES), figsize=(14, 8), dpi=150)

  for i, num_robots in enumerate(robot_counts):
    session_id = SESSIONS[num_robots]
    print(f"Processing session {session_id} ({num_robots} robots)...")

    for j, (episode, stage_name) in enumerate(EPISODE_STAGES):
      ax = axes[i, j]

      # Load frames from JSON
      frames = load_frames_from_json(session_id, episode)

      if frames:
        trajectories, obstacles = extract_trajectories(frames, num_robots)
        title = f"{stage_name}"
        plot_trajectory(ax, trajectories, obstacles, title)
        total_points = sum(len(t) for t in trajectories)
        print(f"  Episode {episode}: {len(frames)} frames, {total_points} trajectory points")
      else:
        ax.set_title(f"{stage_name}\n(no data)", fontsize=9)
        ax.set_xticks([])
        ax.set_yticks([])

    # Add row labels (robot counts)
    axes[i, 0].set_ylabel(
      f"{num_robots} robots", fontsize=10, fontweight="bold", rotation=90, labelpad=10
    )

  plt.tight_layout()
  output_path = f"{OUTPUT_DIR}/multi_agent_trajectories.png"
  plt.savefig(output_path, bbox_inches="tight", facecolor="white")
  plt.close()
  print(f"Saved: {output_path}")


if __name__ == "__main__":
  generate_trajectory_figures()
