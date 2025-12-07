import asyncio
import httpx
import json
import argparse

API_URL = "http://localhost:8000/api/v1/training/start"

async def submit_job(name, coverage, exploration, diversity, threat_penalty, battery_drain, steps, seed):
    config = {
        "name": name,
        "algorithm": "ppo",
        "environment_type": "enhanced",
        "total_timesteps": steps,
        "env_width": 20,
        "env_height": 20,
        "coverage_weight": coverage,
        "exploration_weight": exploration,
        "diversity_weight": diversity,
        "threat_penalty_weight": threat_penalty,
        "battery_drain_rate": battery_drain,
        "num_robots": 3,
        "config": {
            "map_config": {
                "map_type": "random",
                "seed": seed
            }
        }
    }

    async with httpx.AsyncClient() as client:
        try:
            print(f"Submitting job to {API_URL}...")
            print(json.dumps(config, indent=2))
            response = await client.post(API_URL, json=config, timeout=10.0)
            if response.status_code in (200, 202):
                print(f"Success! Job ID: {response.json().get('id')}")
                print(response.json())
                return response.json().get('id')
            else:
                print(f"Failed: {response.status_code}")
                print(response.text)
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="Cycle-02-Coverage")
    parser.add_argument("--steps", type=int, default=100000)
    parser.add_argument("--cov", type=float, default=1.0)
    parser.add_argument("--exp", type=float, default=0.3)
    parser.add_argument("--div", type=float, default=0.2)
    parser.add_argument("--threat", type=float, default=0.0)
    parser.add_argument("--drain", type=float, default=0.001)
    parser.add_argument("--seed", type=int, default=42) # New seed for variety? or same for comparison? Let's use 42 to isolate weight impact.
    
    args = parser.parse_args()
    
    # Keeping seed 42 to strictly compare weight influence on same map
    asyncio.run(submit_job(args.name, args.cov, args.exp, args.div, args.threat, args.drain, args.steps, args.seed))

