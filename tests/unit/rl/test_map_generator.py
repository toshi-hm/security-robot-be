"""Unit tests for MapGenerator."""

from rl.environments.map_generator import (
    CellularAutomataGenerator,
    MazeGenerator,
    RandomObstacleGenerator,
    RoomGenerator,
    create_generator,
)


def test_random_generator():
    gen = create_generator("random", 10, 10, obstacle_count=5)
    assert isinstance(gen, RandomObstacleGenerator)
    grid = gen.generate()
    assert len(grid) == 10
    assert len(grid[0]) == 10

    # Count obstacles
    count = sum(sum(1 for cell in row if cell) for row in grid)
    assert count == 5

def test_maze_generator():
    gen = create_generator("maze", 11, 11) # Odd dimensions for maze
    assert isinstance(gen, MazeGenerator)
    grid = gen.generate()
    assert len(grid) == 11
    assert len(grid[0]) == 11

    # Check boundaries (should be walls mostly, but implementation details vary)
    # Just check it returns a bool grid
    assert isinstance(grid[0][0], bool)

def test_room_generator():
    gen = create_generator("room", 20, 20)
    assert isinstance(gen, RoomGenerator)
    grid = gen.generate()
    assert len(grid) == 20
    assert len(grid[0]) == 20

def test_cave_generator():
    gen = create_generator("cave", 20, 20)
    assert isinstance(gen, CellularAutomataGenerator)
    grid = gen.generate()
    assert len(grid) == 20
    assert len(grid[0]) == 20
