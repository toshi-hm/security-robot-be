"""
Single-agent trajectory visualization using direct database query.
Creates trajectory plot for 1 robot at different training stages.
"""

import os

import matplotlib.patches as patches
import matplotlib.pyplot as plt
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Database connection
DATABASE_URL = "postgresql+psycopg://security_robot:change_me@localhost:5432/security_robot"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

# Configuration
SESSION_ID = 77  # single-agent-enhanced-ppo-metrics

# Episodes to visualize: early, mid, late (including best coverage ep 47)
EPISODE_STAGES = [
  (1, "ep 1"),
  (2, "ep 2"),
  (25, "ep 25"),
  (47, "ep 47"),
  (50, "ep 50"),
]

OUTPUT_DIR = "/home/hama/work/master/masterpj-tex/Figures"

# Robot color
COLOR = "#e41a1c"


def fetch_frames_from_db(session_id: int, episode: int) -> list:
  """Fetch playback frames directly from database for a specific episode."""
  with Session() as db:
    # Try primary table name
    query = text("""
            SELECT robots, obstacles 
            FROM environmentstate 
            WHERE session_id = :session_id AND episode = :episode
            ORDER BY step ASC
            LIMIT 1000
        """)

    try:
      result = db.execute(query, {"session_id": session_id, "episode": episode})
    except Exception:
      # Fallback for table name variations
      try:
        query = text("""
                    SELECT robots, obstacles 
                    FROM environment_states 
                    WHERE session_id = :session_id AND episode = :episode
                    ORDER BY step ASC
                    LIMIT 1000
                """)
        result = db.execute(query, {"session_id": session_id, "episode": episode})
      except Exception as e:
        print(f"Error querying database: {e}")
        return []

    rows = result.fetchall()
    frames = []
    for row in rows:
      robots_data = row[0] if row[0] else []
      obstacles_data = row[1] if row[1] else {}
      frames.append({"robots": robots_data, "obstacles": obstacles_data})
    return frames


def extract_trajectory(frames: list) -> tuple:
  """Extract robot trajectory and obstacles from frames."""
  trajectory = []
  obstacles = set()

  for frame in frames:
    robots = frame.get("robots", [])
    # Robot 0
    if robots and isinstance(robots, list) and len(robots) > 0:
      if isinstance(robots[0], dict):
        x, y = robots[0].get("x", 0), robots[0].get("y", 0)
        trajectory.append((x, y))
    elif robots and isinstance(robots, dict):
      # Might be dict if single robot?
      pass

    if not obstacles:
      obs_data = frame.get("obstacles", {})
      if isinstance(obs_data, dict):
        obs_grid = obs_data.get("levels", [])
        for y_idx, row in enumerate(obs_grid):
          for x_idx, is_obstacle in enumerate(row):
            if is_obstacle:
              obstacles.add((x_idx, y_idx))

  return trajectory, obstacles


def plot_trajectory(ax, trajectory: list, obstacles: set, title: str, grid_size: int = 20):
  """Plot robot trajectory on a grid."""
  ax.set_xlim(-0.5, grid_size - 0.5)
  ax.set_ylim(-0.5, grid_size - 0.5)
  ax.set_aspect("equal")
  ax.invert_yaxis()

  for i in range(grid_size + 1):
    ax.axhline(y=i - 0.5, color="#e0e0e0", linewidth=0.3)
    ax.axvline(x=i - 0.5, color="#e0e0e0", linewidth=0.3)

  for x, y in obstacles:
    rect = patches.Rectangle((x - 0.5, y - 0.5), 1, 1, linewidth=0, facecolor="#404040")
    ax.add_patch(rect)

  if len(trajectory) >= 2:
    # Match multi-agent granularity (downsample to ~200 pts)
    step = max(1, len(trajectory) // 200)
    traj_sampled = trajectory[::step]

    n_points = len(traj_sampled)
    # Use linewidth 1.2 to match multi-agent style
    for j in range(n_points - 1):
      alpha = 0.3 + 0.7 * (j / n_points)
      ax.plot(
        [traj_sampled[j][0], traj_sampled[j + 1][0]],
        [traj_sampled[j][1], traj_sampled[j + 1][1]],
        color=COLOR,
        alpha=alpha,
        linewidth=1.2,
      )

    ax.scatter(
      trajectory[0][0],
      trajectory[0][1],
      color=COLOR,
      s=60,
      marker="o",
      edgecolors="white",
      linewidths=1,
      zorder=10,
    )
    ax.scatter(
      trajectory[-1][0],
      trajectory[-1][1],
      color=COLOR,
      s=60,
      marker="s",
      edgecolors="white",
      linewidths=1,
      zorder=10,
    )

  ax.set_title(title, fontsize=10)
  ax.set_xticks([])
  ax.set_yticks([])


def generate_trajectory_figure():
  """Generate single-agent trajectory visualization figure."""
  os.makedirs(OUTPUT_DIR, exist_ok=True)

  # Create horizontal figure (1 row × 5 columns)
  fig, axes = plt.subplots(1, len(EPISODE_STAGES), figsize=(14, 3), dpi=150)

  print(f"Processing session {SESSION_ID} (1 robot)...")

  for j, (episode, stage_name) in enumerate(EPISODE_STAGES):
    ax = axes[j]

    frames = fetch_frames_from_db(SESSION_ID, episode)

    if frames:
      trajectory, obstacles = extract_trajectory(frames)
      # Trajectory might be empty if parsing fails or no data
      if trajectory:
        plot_trajectory(ax, trajectory, obstacles, stage_name)
        print(f"  Episode {episode}: {len(frames)} frames, {len(trajectory)} trajectory points")
      else:
        print(
          f"  Episode {episode}: {len(frames)} frames, but NO trajectory extracted. Check robots data format."
        )
        # Show empty plot
        ax.set_title(f"{stage_name}\n(no trajectory)", fontsize=10)
        ax.set_xticks([])
        ax.set_yticks([])

    else:
      ax.set_title(f"{stage_name}\n(no data)", fontsize=10)
      ax.set_xticks([])
      ax.set_yticks([])

  plt.tight_layout()
  output_path = f"{OUTPUT_DIR}/single_agent_trajectories.png"
  plt.savefig(output_path, bbox_inches="tight", facecolor="white")
  plt.close()
  print(f"Saved: {output_path}")


if __name__ == "__main__":
  generate_trajectory_figure()
