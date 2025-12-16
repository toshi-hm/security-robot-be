import json


def analyze_results(file_path):
  print(f"Analyzing {file_path}...")
  try:
    with open(file_path) as f:
      lines = f.readlines()
  except FileNotFoundError:
    print(f"File not found: {file_path}")
    return

  data = [json.loads(line) for line in lines]
  total_episodes = len(data)
  print(f"Total Episodes: {total_episodes}")

  if total_episodes == 0:
    return

  # Analyze last 20 episodes or all if less
  recent_count = min(20, total_episodes)
  recent_data = data[-recent_count:]

  avg_coverage = sum(d["coverage"] for d in recent_data) / recent_count
  avg_threat = sum(d["avg_threat"] for d in recent_data) / recent_count
  avg_reward = sum(d["final_reward"] for d in recent_data) / recent_count

  print(f"--- Analysis (Last {recent_count} Episodes) ---")
  print(f"Average Coverage: {avg_coverage:.4f}")
  print(f"Average Threat:   {avg_threat:.4f}")
  print(f"Average Reward:   {avg_reward:.2f}")


if __name__ == "__main__":
  analyze_results("report/result/job_48_episodes.jsonl")
