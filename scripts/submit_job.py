import argparse
import asyncio
import json

import httpx

API_URL = "http://localhost:8000/api/v1/training/start"


async def submit_job(args: argparse.Namespace) -> str | None:
  config = {
    "name": args.name,
    "algorithm": "ppo",
    "environment_type": "enhanced",
    "total_timesteps": args.steps,
    "env_width": 20,
    "env_height": 20,
    "coverage_weight": args.cov,
    "exploration_weight": args.exp,
    "diversity_weight": args.div,
    "threat_penalty_weight": args.threat,
    "battery_drain_rate": args.drain,
    "num_robots": 3,
    "config": {
      "map_config": {"map_type": "random", "seed": args.seed},
      "environment_type": "enhanced",
      "battery_drain_rate": args.drain,
      "threat_penalty_weight": args.threat,
      "strategic_init_mode": args.strategic,
      "episode_log_file": None,  # Placeholder, filled by worker
    },
  }

  async with httpx.AsyncClient() as client:
    try:
      print(f"Submitting job to {API_URL}...")
      print(json.dumps(config, indent=2))
      response = await client.post(API_URL, json=config, timeout=10.0)
      if response.status_code in (200, 202):
        print(f"Success! Job ID: {response.json().get('id')}")
        print(response.json())
        return str(response.json().get("id"))
      else:
        print(f"Failed: {response.status_code}")
        print(response.text)
        return None
    except Exception as e:
      print(f"Error: {e}")
      return None


if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("--name", default="Cycle-02-Coverage")
  parser.add_argument("--steps", type=int, default=100000)
  parser.add_argument("--cov", type=float, default=1.0)
  parser.add_argument("--exp", type=float, default=0.3)
  parser.add_argument("--div", type=float, default=0.2)
  parser.add_argument("--threat", type=float, default=0.0)
  parser.add_argument("--drain", type=float, default=0.001, help="Battery drain rate")
  parser.add_argument("--strategic", action="store_true", help="Enable strategic initialization")
  parser.add_argument("--seed", type=int, default=42, help="Map seed")

  args = parser.parse_args()

  asyncio.run(submit_job(args))
