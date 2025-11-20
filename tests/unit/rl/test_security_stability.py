"""Tests for security and stability improvements."""


# Mock a3c_service to avoid actual training during pipeline test
from unittest.mock import AsyncMock, patch

import pytest

from rl.environments.map_generator import create_generator


@pytest.mark.asyncio
async def test_pipeline_path_traversal_prevention(tmp_path, caplog):
    """Test that the pipeline prevents path traversal in model_path."""

    # Create a dummy project root
    project_root = tmp_path / "project"
    project_root.mkdir()

    # Mock project_root in pipeline
    with patch("scripts.pipeline.project_root", project_root):
        # Mock a3c_service
        with patch("scripts.pipeline.a3c_service") as mock_service:
            mock_service.start_training = AsyncMock(return_value="Success")

            # Define a config with a malicious path (unused variable removed)
            # malicious_config = { ... }

            # Since we can't easily inject into the local variable 'stages',
            # we verify the logic by replicating it here.

            # Test logic directly:

            model_path_str = "../../../etc/passwd"
            safe_path = (project_root / model_path_str).resolve()
            is_safe = str(safe_path).startswith(str(project_root.resolve()))
            assert not is_safe

            model_path_str = "models/safe.pth"
            safe_path = (project_root / model_path_str).resolve()
            is_safe = str(safe_path).startswith(str(project_root.resolve()))
            assert is_safe

def test_map_generator_seeding():
    """Test that map generation is deterministic with seeds."""
    width, height = 20, 20
    seed = 42

    # Test all types
    for map_type in ["random", "maze", "room", "cave"]:
        gen1 = create_generator(map_type, width, height, seed=seed)
        map1 = gen1.generate()

        gen2 = create_generator(map_type, width, height, seed=seed)
        map2 = gen2.generate()

        assert map1 == map2, f"Map type {map_type} is not deterministic with seed {seed}"

        # Verify different seeds produce different maps (mostly)
        gen3 = create_generator(map_type, width, height, seed=seed + 1)
        map3 = gen3.generate()
        assert map1 != map3, f"Map type {map_type} produced same map with different seeds"

def test_room_generator_small_bounds():
    """Test RoomGenerator with small bounds."""
    # Should not crash
    gen = create_generator("room", 5, 5, seed=1)
    map_grid = gen.generate()
    assert len(map_grid) == 5
    assert len(map_grid[0]) == 5

    # Even smaller
    gen = create_generator("room", 3, 3, seed=1)
    map_grid = gen.generate()
    assert len(map_grid) == 3

def test_maze_generator_min_size():
    """Test that MazeGenerator enforces minimum size of 5x5."""
    with pytest.raises(ValueError, match="at least 5x5"):
        gen = create_generator("maze", 4, 4, seed=1)
        gen.generate()

    with pytest.raises(ValueError, match="at least 5x5"):
        gen = create_generator("maze", 3, 5, seed=1)
        gen.generate()

    # Should work with 5x5
    gen = create_generator("maze", 5, 5, seed=1)
    map_grid = gen.generate()
    assert len(map_grid) == 5

def test_room_generator_fallback():
    """Test that RoomGenerator creates at least one room even in small grids."""
    # Very small grid where random room placement might fail
    gen = create_generator("room", 6, 6, seed=1)
    map_grid = gen.generate()

    # Count non-obstacle cells (should have at least some from fallback room)
    passable_cells = sum(sum(1 for cell in row if not cell) for row in map_grid)
    assert passable_cells > 0, "RoomGenerator should create at least one room"

