import argparse
from collections import defaultdict
import json
import sys

import numpy as np


def load_data(file_path: str) -> list[dict]:
  data = []
  try:
    with open(file_path) as f:
      for line in f:
        try:
          data.append(json.loads(line))
        except json.JSONDecodeError:
          pass
  except FileNotFoundError:
    print(f"Error: File {file_path} not found.")
    sys.exit(1)
  return data


def generate_heatmap(file_path: str, metric: str = "final_reward", reduce_op: str = "mean") -> None:
  data = load_data(file_path)
  if not data:
    print("No data found.")
    return

  # Grid size
  width, height = 20, 20

  # Store values for each cell
  # cell_values[(x,y)] = [val1, val2, ...]
  cell_values: dict[tuple[int, int], list[float]] = defaultdict(list)

  total_episodes = len(data)
  print(f"Processing {total_episodes} episodes...")

  for episode in data:
    # Get metric
    val = episode.get(metric)
    if val is None:
      continue

    # Get start positions
    # e.g., [[x1, y1], [x2, y2], [x3, y3]]
    starts = episode.get("start_positions", [])

    # Attribute the EPISODE's result to EACH robot's starting position
    # Assumption: If this was a good episode, these were good start positions (on average)
    for pos in starts:
      if len(pos) == 2:
        x, y = pos
        if 0 <= x < width and 0 <= y < height:
          cell_values[(x, y)].append(val)

  # Calculate heatmap
  heatmap = np.zeros((height, width))
  count_map = np.zeros((height, width))

  for y in range(height):
    for x in range(width):
      vals = cell_values.get((x, y), [])
      if vals:
        count_map[y, x] = len(vals)
        if reduce_op == "mean":
          heatmap[y, x] = np.mean(vals)
        elif reduce_op == "max":
          heatmap[y, x] = np.max(vals)
        elif reduce_op == "min":
          heatmap[y, x] = np.min(vals)
      else:
        heatmap[y, x] = np.nan  # Or MIN_VAL

  # Visualize
  # Normalize for display? Not needed for raw values, but good for heatmap.

  valid_cells = count_map > 0
  if not np.any(valid_cells):
    print("No valid cells mapped.")
    return

  min_val = np.nanmin(heatmap)
  max_val = np.nanmax(heatmap)

  print(f"\nHeatmap Analysis ({metric}, {reduce_op})")
  print(f"Range: {min_val:.2f} to {max_val:.2f}")

  # Filter valid cells for sorting
  valid_indices = []
  valid_values = []
  for y in range(height):
    for x in range(width):
      if count_map[y, x] > 0:
        idx = y * width + x
        valid_indices.append(idx)
        valid_values.append(heatmap[y, x])

  valid_indices_arr = np.array(valid_indices)
  valid_values_arr = np.array(valid_values)

  if len(valid_values_arr) > 0:
    # Sort by value (ascending)
    sorted_order = np.argsort(valid_values_arr)
    # Take top 5 (last 5)
    top_indices = valid_indices_arr[sorted_order][-5:][::-1]

    print("\nTop 5 Start Positions:")
    for idx in top_indices:
      y, x = divmod(idx, width)
      print(f"({x}, {y}): {heatmap[y, x]:.2f} (n={int(count_map[y, x])})")
  else:
    print("No valid data for ranking.")

  # ASCII Visualization (Simplified)
  # 0..9 scale
  print("\nGrid Visualization (0-9, . = no data):")
  print("   " + "".join([f"{i % 10}" for i in range(width)]))

  normalized = (heatmap - min_val) / (max_val - min_val + 1e-9)

  for y in range(height):
    row_str = f"{y:2d} "
    for x in range(width):
      if count_map[y, x] == 0:
        row_str += "."
      else:
        val = int(normalized[y, x] * 9)
        row_str += str(val)
    print(row_str)


if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("file", help="Path to episodes.jsonl")
  parser.add_argument("--metric", default="final_reward", help="coverage or final_reward")
  args = parser.parse_args()

  generate_heatmap(args.file, args.metric)
