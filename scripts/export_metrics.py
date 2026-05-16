import csv
import sys
import asyncio
import httpx
import math
import os

API_URL_BASE = "http://localhost:8000/api/v1"

async def get_job_status(client, job_id):
  try:
    resp = await client.get(f"{API_URL_BASE}/training/{job_id}/status")
    if resp.status_code == 200:
      return resp.json()
  except:
    pass
  return {}

async def get_all_metrics(client, job_id):
  all_metrics = []
  page = 1
  page_size = 500
  
  while True:
    try:
      resp = await client.get(f"{API_URL_BASE}/training/sessions/{job_id}/metrics?page={page}&page_size={page_size}")
      if resp.status_code != 200:
        break
      
      data = resp.json()
      metrics = data.get("metrics", [])
      if not metrics:
        break
        
      all_metrics.extend(metrics)
      
      if len(metrics) < page_size:
        break
      page += 1
    except Exception as e:
      print(f"Error fetching metrics page {page}: {e}")
      break
      
  # Sort by timestep
  all_metrics.sort(key=lambda x: x["timestep"])
  return all_metrics

async def main():
  if len(sys.argv) < 2:
    print("Usage: python scripts/export_metrics.py <job_ids> (comma separated)")
    sys.exit(1)

  job_ids = [int(x) for x in sys.argv[1].split(",")]

  async with httpx.AsyncClient() as client:
    for job_id in job_ids:
      print(f"Processing Job {job_id}...")
      
      status = await get_job_status(client, job_id)
      metrics = await get_all_metrics(client, job_id)
      
      if not metrics:
        print(f"  No metrics found for Job {job_id}")
        continue
        
      # Determine normalization info for estimation
      # Check config if not in top level
      config = status.get("config") or {}
      num_robots = status.get("num_robots") or config.get("num_robots", 1)
      norm_mode = status.get("reward_normalization_mode") or config.get("reward_normalization_mode", "mean")
      
      # Filename
      filename = f"job_{job_id}_metrics.csv"
      
      # Headers
      headers = [
        "timestep", "episode", "reward", "estimated_team_reward", 
        "coverage_ratio", "threat_level_avg", "exploration_score", 
        "loss", "timestamp"
      ]
      
      with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        
        for m in metrics:
          # Extract standard fields
          row = {
            "timestep": m["timestep"],
            "episode": m["episode"],
            "reward": m["reward"],
            "coverage_ratio": m["coverage_ratio"],
            "threat_level_avg": m["threat_level_avg"],
            "exploration_score": m["exploration_score"],
            "loss": m["loss"],
            "timestamp": m["timestamp"]
          }
          
          # Calculate estimated team reward
          # First check if actual team_reward exists in additional_metrics
          add_metrics = m.get("additional_metrics")
          team_reward = None
          
          if add_metrics and "team_reward" in add_metrics:
            team_reward = add_metrics["team_reward"]
          
          if team_reward is None:
             # Fallback estimation
             r = m["reward"] or 0.0
             if norm_mode == "mean":
               team_reward = r * num_robots
             elif norm_mode == "sqrt_mean":
               team_reward = r * math.sqrt(num_robots)
             else: # sum
               team_reward = r
          
          row["estimated_team_reward"] = team_reward
          writer.writerow(row)
          
      print(f"  Exported {len(metrics)} records to {filename}")

if __name__ == "__main__":
  asyncio.run(main())
