import argparse
import asyncio
import httpx
import json

API_URL_BASE = "http://localhost:8000/api/v1"

async def get_job_details(client, job_id):
  try:
    response = await client.get(f"{API_URL_BASE}/training/{job_id}/status")
    if response.status_code != 200:
      return None
    return response.json()
  except Exception:
    return None

async def get_metrics(client, job_id):
  try:
    # Get metrics, page size 50
    response = await client.get(f"{API_URL_BASE}/training/sessions/{job_id}/metrics?page=1&page_size=50")
    if response.status_code != 200:
      return []
    return response.json().get("metrics", [])
  except Exception:
    return []

def calculate_mean(values):
  if not values:
    return 0.0
  return sum(values) / len(values)

async def main():
  parser = argparse.ArgumentParser(description="Compare training experiments")
  parser.add_argument("job_ids", type=str, help="Comma-separated job IDs (e.g. 59,60,61,62)")
  args = parser.parse_args()

  job_ids = [int(jid) for jid in args.job_ids.split(",")]

  results = []

  async with httpx.AsyncClient() as client:
    for job_id in job_ids:
      print(f"Fetching data for Job {job_id}...")
      
      details = await get_job_details(client, job_id)
      if not details:
        print(f"  Failed the fetch details for Job {job_id}")
        continue
        
      metrics = await get_metrics(client, job_id)
      if not metrics:
        print(f"  No metrics found for Job {job_id}")
        continue

      # Extract config info
      num_robots = details.get("num_robots")
      if num_robots is None:
          config = details.get("config") or {}
          num_robots = config.get("num_robots", "?")

      norm_mode = details.get("reward_normalization_mode")
      if norm_mode is None:
          config = details.get("config") or {}
          norm_mode = config.get("reward_normalization_mode", "mean")
      
      # Sort by timestep
      metrics.sort(key=lambda x: x['timestep'])
      last_metrics = metrics[-10:]

      # Calculate averages
      cov_vals = [m['coverage_ratio'] for m in last_metrics if m['coverage_ratio'] is not None]
      avg_coverage = calculate_mean(cov_vals)

      threat_vals = [m['threat_level_avg'] for m in last_metrics if m['threat_level_avg'] is not None]
      avg_threat = calculate_mean(threat_vals)

      reward_vals = [m['reward'] for m in last_metrics]
      avg_reward = calculate_mean(reward_vals)
      
      avg_team_reward = 0.0
      team_rewards = []
      for m in last_metrics:
        add_metrics = m.get('additional_metrics') or {}
        tr = add_metrics.get('team_reward')
        if tr is not None:
          team_rewards.append(tr)
      
      if team_rewards:
        avg_team_reward = calculate_mean(team_rewards)
      else:
        # Fallback
        if norm_mode == "mean" and isinstance(num_robots, int):
           avg_team_reward = avg_reward * num_robots
        else:
           avg_team_reward = avg_reward

      results.append({
        "id": job_id,
        "name": details['name'][:30], # Truncate
        "robots": num_robots,
        "mode": norm_mode,
        "cov": avg_coverage,
        "threat": avg_threat,
        "reward": avg_reward,
        "team_reward": avg_team_reward
      })

  print("\n" + "="*95)
  print(f"{'ID':<4} | {'Robots':<6} | {'Mode':<6} | {'Cov':<6} | {'Threat':<6} | {'Reward':<8} | {'TeamRew':<8} | {'Name':<30}")
  print("-" * 95)
  
  for r in results:
    print(f"{r['id']:<4} | {r['robots']:<6} | {r['mode']:<6} | {r['cov']:.4f} | {r['threat']:.4f} | {r['reward']:<8.1f} | {r['team_reward']:<8.1f} | {r['name']}")
    
  print("="*95)
