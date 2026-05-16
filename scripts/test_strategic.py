import logging
import sys

from rl.environments.enhanced_env import OPTIMAL_START_POSITIONS, EnhancedSecurityEnvironment


def test_strategic_init() -> None:
  print("Testing Strategic Initialization...")

  # Initialize env with strategic mode
  env = EnhancedSecurityEnvironment(num_robots=3, strategic_init_mode=True, battery_drain_rate=0.1)

  print("Environment initialized.")

  failures = 0
  trials = 10

  print(f"Running {trials} resets...")
  for i in range(trials):
    env.reset()

    # But we want internal state `episode_start_positions`.
    start_positions = env.episode_start_positions
    print(f"Trial {i + 1}: Starts={start_positions}")

    # Verify each position is in OPTIMAL_START_POSITIONS
    # Note: OPTIMAL_START_POSITIONS are tuples.
    # start_positions might be lists or tuples depending on internal storage.

    optimal_set = set(OPTIMAL_START_POSITIONS)

    for pos in start_positions:
      # pos is (x, y)
      if pos not in optimal_set:
        print(f"FAILURE: Position {pos} is NOT in optimal set!")
        failures += 1
      else:
        # print(f"  OK: {pos}")
        pass

    if len(set(start_positions)) != 3:
      print("FAILURE: Duplicate positions found!")
      failures += 1

  if failures == 0:
    print("\nSUCCESS: All trials used optimal positions.")
  else:
    print(f"\nFAILURE: {failures} issues detected.")
    sys.exit(1)


if __name__ == "__main__":
  logging.basicConfig(level=logging.WARN)
  test_strategic_init()
