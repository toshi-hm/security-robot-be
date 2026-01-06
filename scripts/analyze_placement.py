import sys

import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Database connection
DATABASE_URL = "postgresql+psycopg://security_robot:change_me@localhost:5432/security_robot"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def fetch_episode_stats(session_id):
  with Session() as db:
    # Fetch start positions (step 0 or 1)
    # We need to find the first step of each episode
    query = text("""
            SELECT episode, robots, obstacles
            FROM environmentstate
            WHERE session_id = :session_id
            AND step = 0
            ORDER BY episode ASC
        """)
    # Fallback table names if needed (omitted for brevity, assume environmentstate works as verified)
    try:
      result = db.execute(query, {"session_id": session_id})
      start_rows = result.fetchall()
    except:
      # Try environment_states
      query = text("""
                SELECT episode, robots, obstacles
                FROM environment_states
                WHERE session_id = :session_id
                AND step = 0
                ORDER BY episode ASC
            """)
      result = db.execute(query, {"session_id": session_id})
      start_rows = result.fetchall()

    # Fetch episode metrics
    metric_query = text("""
            SELECT episode, MAX(reward) as reward, MAX(coverage_ratio) as coverage_ratio, AVG(threat_level_avg) as threat
            FROM trainingmetric
            WHERE job_id = :session_id
            GROUP BY episode
            ORDER BY episode ASC
        """)
    try:
      metric_res = db.execute(metric_query, {"session_id": session_id}).fetchall()
    except Exception as e:
      print(f"Error fetching metrics: {e}")
      metric_res = []

  # Helper to calc mean
  def calc_stats(rows):
    if not rows:
      return 0, 0, 0
    rs = [r.reward for r in rows]
    cs = [r.coverage_ratio for r in rows]
    ts = [r.threat for r in rows]
    return np.mean(rs), np.std(rs), np.mean(cs), np.std(cs), np.mean(ts), np.std(ts)

  # Convert to dict
  ep_map = {r.episode: r for r in metric_res}

  ranges = [(1, 10, "1-10"), (40, 49, "40-49"), (41, 50, "41-50"), (0, 9, "0-9")]

  print(f"\nStats for Job {session_id}:")
  for start, end, label in ranges:
    data_rows = [ep_map[e] for e in range(start, end + 1) if e in ep_map]
    rm, rstd, cm, cstd, tm, tstd = calc_stats(data_rows)
    print(
      f"Range {label} (n={len(data_rows)}): Rew={rm:.1f}±{rstd:.1f}, Cov={cm:.3f}±{cstd:.3f}, Threat={tm:.3f}±{tstd:.3f}"
    )

  start_pos_map = {}
  for r in start_rows:
    ep = r[0]
    robots = r[1]
    if robots:
      # Extract (x,y) for all robots
      positions = []
      if isinstance(robots, list):
        for bot in robots:
          if isinstance(bot, dict):
            positions.append((bot.get("x"), bot.get("y")))
      start_pos_map[ep] = positions

  data = []
  for m in metric_res:
    ep = m[0]
    reward = m[1]
    cov = m[2]
    threat = m[3]
    if ep in start_pos_map:
      starts = start_pos_map[ep]
      data.append(
        {"episode": ep, "starts": starts, "reward": reward, "coverage": cov, "threat": threat}
      )
  return data


def analyze_single_agent(data):
  print(f"Analyzing {len(data)} episodes...")
  # 1. Heatmap of start positions (early vs late)
  grid_w, grid_h = 20, 20
  heatmap_all = np.zeros((grid_h, grid_w))
  heatmap_late = np.zeros((grid_h, grid_w))

  rewards_by_pos = {}  # (x,y) -> [rewards]

  late_threshold = max(1, len(data) - 20)

  for d in data:
    if not d["starts"]:
      continue
    sx, sy = d["starts"][0]
    heatmap_all[sy, sx] += 1

    if (sx, sy) not in rewards_by_pos:
      rewards_by_pos[(sx, sy)] = []
    rewards_by_pos[(sx, sy)].append(d["reward"])

    if d["episode"] >= late_threshold:
      heatmap_late[sy, sx] += 1

  # Find best starting positions
  avg_rewards = []
  for pos, rews in rewards_by_pos.items():
    avg_rewards.append((pos, np.mean(rews), len(rews)))

  avg_rewards.sort(key=lambda x: x[1], reverse=True)

  print("\nTop 5 Starting Positions (by Avg Reward):")
  for pos, r, count in avg_rewards[:5]:
    print(f"  {pos}: Reward={r:.1f} (n={count})")

  print("\nWorst 5 Starting Positions:")
  for pos, r, count in avg_rewards[-5:]:
    print(f"  {pos}: Reward={r:.1f} (n={count})")

  # Center preference?
  center_x, center_y = grid_w / 2, grid_h / 2

  dists = []
  rews = []
  for d in data:
    if not d["starts"]:
      continue
    sx, sy = d["starts"][0]
    dist = np.sqrt((sx - center_x) ** 2 + (sy - center_y) ** 2)
    dists.append(dist)
    rews.append(d["reward"])

  corr = np.corrcoef(dists, rews)[0, 1]
  print(f"\nCorrelation between Distance-from-Center and Reward: {corr:.3f}")

  # Late stage convergence
  print("\nLate Stage Start Positions (Last 20 eps):")
  late_data = [d for d in data if d["episode"] >= late_threshold]
  for d in late_data:
    print(
      f"  Ep {d['episode']}: {d['starts'][0]} -> R={d['reward']:.0f}, Cov={d['coverage']:.3f}, T={d['threat']:.3f}"
    )


if __name__ == "__main__":
  if len(sys.argv) < 2:
    print("Usage: python analyze_placement.py <session_id>")
    sys.exit(1)

  sid = int(sys.argv[1])
  data = fetch_episode_stats(sid)
  analyze_single_agent(data)
