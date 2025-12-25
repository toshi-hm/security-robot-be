"""
Cycle 12実験の再現とロボット台数変更実験を実行するスクリプト。

- Cycle 12 (num_robots=3) を再現
- その後、num_robots=2,3,4,5 のバリエーションをキューに投入

使用方法:
  python scripts/submit_cycle_12_variants.py --dry-run   # 確認のみ
  python scripts/submit_cycle_12_variants.py             # 実際に投入
  python scripts/submit_cycle_12_variants.py --robots "3,5" --normalization-mode sum # 正規化モード指定
"""

import argparse
import asyncio
import json

import httpx

API_URL = "http://localhost:8000/api/v1/training/start"


def create_cycle_12_config(num_robots: int, name_suffix: str = "", normalization_mode: str = "mean") -> dict:
  """Cycle 12のパラメータでジョブ設定を生成。"""
  name = f"Cycle12-Robots{num_robots}{name_suffix}"
  if normalization_mode != "mean":
    name += f"-{normalization_mode}"

  return {
    "name": name,
    "algorithm": "ppo",
    "environment_type": "enhanced",
    "total_timesteps": 100000,
    "env_width": 20,
    "env_height": 20,
    "coverage_weight": 1.0,
    "exploration_weight": 0.5,
    "diversity_weight": 0.5,
    "threat_penalty_weight": 50.0,
    "battery_drain_rate": 0.001,
    "num_robots": num_robots,
    "reward_normalization_mode": normalization_mode,
    "config": {
      "map_config": {"map_type": "random", "seed": 42},
      "environment_type": "enhanced",
      "battery_drain_rate": 0.001,
      "threat_penalty_weight": 50.0,
      "strategic_init_mode": False,
      "episode_log_file": None,
      "reward_normalization_mode": normalization_mode,
    },
  }


async def submit_job(config: dict, dry_run: bool = False) -> str | None:
  """ジョブをAPIに投入。dry_runがTrueの場合は投入せずに表示のみ。"""
  print(f"\n{'='*60}")
  print(f"Job: {config['name']}")
  print(f"  num_robots: {config['num_robots']}")
  print(f"  total_timesteps: {config['total_timesteps']}")
  print(f"  reward weights: cov={config['coverage_weight']}, exp={config['exploration_weight']}, div={config['diversity_weight']}")
  print(f"  reward_normalization_mode: {config.get('reward_normalization_mode', 'mean')}")
  print(f"  threat_penalty_weight: {config['threat_penalty_weight']}")
  print(f"  battery_drain_rate: {config['battery_drain_rate']}")
  
  if dry_run:
    print("  [DRY RUN - Not submitted]")
    return None

  async with httpx.AsyncClient() as client:
    try:
      response = await client.post(API_URL, json=config, timeout=30.0)
      if response.status_code in (200, 202):
        job_id = response.json().get("id")
        print(f"  ✓ Success! Job ID: {job_id}")
        return str(job_id)
      else:
        print(f"  ✗ Failed: {response.status_code}")
        print(f"    {response.text}")
        return None
    except httpx.ConnectError:
      print("  ✗ Error: Cannot connect to API. Is the server running?")
      return None
    except Exception as e:
      print(f"  ✗ Error: {e}")
      return None


async def main():
  parser = argparse.ArgumentParser(
    description="Cycle 12 再現 & ロボット台数変更実験"
  )
  parser.add_argument(
    "--dry-run", 
    action="store_true", 
    help="投入せずに設定を確認のみ"
  )
  parser.add_argument(
    "--robots",
    type=str,
    default="3,2,3,4,5",
    help="投入するロボット台数のカンマ区切りリスト (default: 3,2,3,4,5 = Cycle12再現 + 2~5台)"
  )
  parser.add_argument(
    "--normalization-mode",
    type=str,
    default="mean",
    choices=["mean", "sum", "sqrt_mean"],
    help="Reward normalization mode (mean, sum, sqrt_mean). Default: mean"
  )
  args = parser.parse_args()

  robot_counts = [int(x.strip()) for x in args.robots.split(",")]
  
  print("=" * 60)
  print("Cycle 12 再現 & ロボット台数変更実験")
  print("=" * 60)
  print(f"\nロボット台数: {robot_counts}")
  print(f"Normalization Mode: {args.normalization_mode}")
  print(f"Dry run: {args.dry_run}")

  submitted_jobs = []
  for i, num_robots in enumerate(robot_counts):
    suffix = "-baseline" if i == 0 else ""
    config = create_cycle_12_config(num_robots, suffix, args.normalization_mode)
    job_id = await submit_job(config, dry_run=args.dry_run)
    if job_id:
      submitted_jobs.append((num_robots, job_id))
    # 連続投入時に少し待つ
    await asyncio.sleep(0.5)

  print("\n" + "=" * 60)
  print("Summary")
  print("=" * 60)
  if args.dry_run:
    print(f"[DRY RUN] Would submit {len(robot_counts)} jobs")
  else:
    print(f"Submitted {len(submitted_jobs)}/{len(robot_counts)} jobs")
    for num_robots, job_id in submitted_jobs:
      print(f"  - Robots: {num_robots} -> Job ID: {job_id}")

  if not args.dry_run and submitted_jobs:
    print("\n解析コマンドの例:")
    print("  python scripts/analyze_cycle_12_results.py --job-ids " + ",".join(j[1] for j in submitted_jobs))


if __name__ == "__main__":
  asyncio.run(main())
