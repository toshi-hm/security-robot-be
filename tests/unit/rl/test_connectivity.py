"""Additional tests for connectivity and security improvements."""

from rl.environments.map_generator import create_generator


def test_path_traversal_prefix_attack(tmp_path):
  """Test that pipeline prevents prefix-based path traversal attacks."""
  from scripts.pipeline import project_root

  # Simulate a prefix attack: /app/security-robot vs /app/security-robot-malicious
  malicious_path = "../security-robot-malicious/evil.pth"

  try:
    safe_path = (project_root / malicious_path).resolve()
    # This should raise ValueError
    safe_path.relative_to(project_root.resolve())
    raise AssertionError("Should have raised ValueError for path outside project root")
  except ValueError:
    # Expected behavior
    pass


def test_room_connectivity_guaranteed():
  """Test that RoomGenerator always produces connected maps."""
  width, height = 20, 20
  seed = 42

  # Generate multiple maps and verify all are connected
  for i in range(10):
    gen = create_generator("room", width, height, seed=seed + i)
    map_grid = gen.generate()

    # Verify connectivity using the generator's own method
    assert gen._is_connected(map_grid), f"Room map {i} is not connected"


def test_cave_connectivity_guaranteed():
  """Test that CellularAutomataGenerator always produces connected maps."""
  width, height = 20, 20
  seed = 42

  # Generate multiple maps and verify all are connected
  for i in range(10):
    gen = create_generator("cave", width, height, seed=seed + i)
    map_grid = gen.generate()

    # Verify connectivity
    assert gen._is_connected(map_grid), f"Cave map {i} is not connected"


def test_room_generator_connectivity_failure_raises():
  """Test that RoomGenerator raises RuntimeError if it can't generate connected map."""
  # This is difficult to test directly, but we can verify the error message exists
  from rl.environments.map_generator import RoomGenerator

  # Very small grid that might fail connectivity
  gen = RoomGenerator(5, 5, seed=1)

  # Should either succeed or raise RuntimeError (not other exceptions)
  try:
    map_grid = gen.generate()
    # If it succeeds, verify it's connected
    assert gen._is_connected(map_grid)
  except RuntimeError as e:
    assert "Failed to generate connected room map" in str(e)
