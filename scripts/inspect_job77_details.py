import json
import subprocess

SESSION_ID = 77


def fetch_metrics(session_id: int):
  all_metrics = []
  for page in range(1, 10):
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


def main():
  metrics = fetch_metrics(SESSION_ID)
  print(f"Fetched {len(metrics)} records for Job {SESSION_ID}")

  # Group by episode
  episodes = {}
  for m in metrics:
    ep = m.get("episode", 0)
    if ep == 0:
      continue

    # We want the LAST metric for each episode to get final coverage/stats
    if ep not in episodes or m.get("timestep", 0) > episodes[ep].get("timestep", 0):
      episodes[ep] = m

  # 1. Validate Max Coverage
  sorted_eps = sorted(episodes.keys())
  print("\n--- Coverage by Episode ---")
  max_cov = -1.0
  max_ep = -1

  for ep in sorted_eps:
    cov = episodes[ep].get("coverage_ratio", 0)
    print(f"Ep {ep}: {cov:.3f}")
    if cov > max_cov:
      max_cov = cov
      max_ep = ep

  print(f"\nMax Coverage: {max_cov:.3f} at Episode {max_ep}")

  # 2. Investigate Episode 50
  if 50 in episodes:
    e50 = episodes[50]
    print("\n--- Episode 50 Details ---")
    print(f"Coverage: {e50.get('coverage_ratio')}")
    print(f"Reward: {e50.get('reward')}")
    print(
      f"Steps: {e50.get('step')}"
    )  # This might be total steps? Logic in plotting script uses 'timestep' but metric has 'step' or 'timestep'
    # Check if it finished early?
    # Standard episode length is 4000? Or 2000?
    # Total timesteps 200,000 / 50 eps = 4000 steps/ep.
    # Let's check the step count of Ep 50 vs Ep 48.

    # Get count of metrics for ep 50 to see duration
    ep50_metrics = [m for m in metrics if m.get("episode") == 50]
    print(f"Metric count for Ep 50: {len(ep50_metrics)}")

    # Compare with Ep 48
    if 48 in episodes:
      e48 = episodes[48]
      print("\n--- Episode 48 Details ---")
      print(f"Coverage: {e48.get('coverage_ratio')}")
      print(f"Reward: {e48.get('reward')}")
      ep48_metrics = [m for m in metrics if m.get("episode") == 48]
      print(f"Metric count for Ep 48: {len(ep48_metrics)}")


if __name__ == "__main__":
  main()
