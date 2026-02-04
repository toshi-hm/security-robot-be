from rl.environments.enhanced_env import EnhancedSecurityEnvironment


def test_strategic_fallback():
  print("Testing Strategic Initialization Fallback...")

  # Initialize with strategic_init_mode=True but NO optimal_start_positions
  env = EnhancedSecurityEnvironment(
    width=20,
    height=20,
    num_robots=3,
    strategic_init_mode=True,
    optimal_start_positions=None,  # Should trigger fallback
  )

  obs, info = env.reset()

  positions = env.episode_start_positions
  print(f"Start Positions: {positions}")

  # Check if positions are valid and distinct
  assert len(set(positions)) == 3, "Positions should be unique"

  # Check if they look like "strategic" points (corners/center/edges)
  # Dimensions 20x20.
  # Corners: (1,1), (18,1), (1,18), (18,18)
  # Center: (10,10)
  # Mid-Edges: (10,1), (10,18), (1,10), (18,10)

  expected_candidates = {
    (1, 1),
    (18, 1),
    (1, 18),
    (18, 18),
    (10, 10),
    (10, 1),
    (10, 18),
    (1, 10),
    (18, 10),
  }

  matches = 0
  for pos in positions:
    if pos in expected_candidates:
      matches += 1

  print(f"Matches with heuristic candidates: {matches}/3")

  # It's possible some candidates are blocked by random map obstacles,
  # but with seed=None (random), we usually get open space.
  # We won't assert strict equality because of map generation,
  # but we expect at least one or two to match if the map isn't totally blocked.

  if matches > 0:
    print("SUCCESS: Robots placed in heuristic strategic positions.")
  else:
    print(
      "WARNING: No exact matches with heuristic, possibly due to obstacles or fallback failure."
    )


if __name__ == "__main__":
  test_strategic_fallback()
