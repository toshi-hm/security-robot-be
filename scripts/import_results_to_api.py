import json

import requests

API_BASE = "http://localhost:8000/api/v1"


def create_session(name, config_override):
  print(f"Creating session: {name}")
  payload = {
    "name": name,
    "algorithm": "ppo",
    "environment_type": "enhanced",
    "total_timesteps": 100000,
    "env_width": 20,
    "env_height": 20,
    "num_robots": 3,
    "config": config_override,
  }
  # Populate default weights if not in config
  payload["coverage_weight"] = config_override.get("coverage_weight", 1.0)
  payload["exploration_weight"] = config_override.get("exploration_weight", 0.5)
  payload["diversity_weight"] = config_override.get("diversity_weight", 0.5)

  try:
    resp = requests.post(f"{API_BASE}/training/start", json=payload)
    resp.raise_for_status()
    session = resp.json()
    print(f"Session created: ID={session['id']}")
    return session["id"]
  except Exception as e:
    print(f"Failed to create session: {e}")
    if hasattr(e, "response") and e.response:
      print(e.response.text)
    return None


def import_episodes(session_id, jsonl_path):
  print(f"Importing episodes from {jsonl_path}...")
  metrics = []

  try:
    with open(jsonl_path) as f:
      lines = f.readlines()
  except FileNotFoundError:
    print(f"File not found: {jsonl_path}")
    return

  for i, line in enumerate(lines):
    data = json.loads(line)
    episode_num = i + 1
    steps = data.get("steps", 1600)
    timestep = episode_num * steps

    # Mapping properties
    metric = {
      "job_id": session_id,
      "timestep": timestep,
      "episode": episode_num,
      "reward": data.get("final_reward", 0.0),
      "coverage_ratio": data.get("coverage", 0.0),
      "threat_level_avg": data.get("avg_threat", 0.0),
      # "loss" is not in log, leave null/None
    }
    metrics.append(metric)

  if not metrics:
    print("No metrics to import.")
    return

  # Bulk Insert
  try:
    resp = requests.post(f"{API_BASE}/training/{session_id}/metrics", json=metrics)
    resp.raise_for_status()
    print(f"Successfully imported {len(metrics)} metrics to Session {session_id}")
  except Exception as e:
    print(f"Failed to import metrics: {e}")
    if hasattr(e, "response") and e.response:
      print(e.response.text)


def main():
  # Cycle 11
  c11_config = {
    "coverage_weight": 1.0,
    "exploration_weight": 0.5,
    "diversity_weight": 0.5,
    "threat_penalty_weight": 50.0,
    "battery_drain_rate": 0.001,
  }
  sid_11 = create_session("Cycle-11-Coordination-Imported", c11_config)
  if sid_11:
    import_episodes(sid_11, "report/result/job_47_episodes.jsonl")
    # Mark as stopped (completed) roughly
    requests.post(f"{API_BASE}/training/{sid_11}/stop?force=true")

  # Cycle 12
  c12_config = {
    "coverage_weight": 1.0,
    "exploration_weight": 0.5,
    "diversity_weight": 0.5,
    "threat_penalty_weight": 50.0,
    "battery_drain_rate": 0.001,
    # Dynamic Radius handling is internal logic, not config param in payload yet explicitly
  }
  sid_12 = create_session("Cycle-12-Efficiency-Imported", c12_config)
  if sid_12:
    import_episodes(sid_12, "report/result/job_48_episodes.jsonl")
    requests.post(f"{API_BASE}/training/{sid_12}/stop?force=true")


if __name__ == "__main__":
  main()
