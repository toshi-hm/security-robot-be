"""Map generation strategies for security environments."""

from __future__ import annotations

import abc
import random
from typing import Literal


class MapGenerator(abc.ABC):
  """Abstract base class for map generation strategies."""

  def __init__(self, width: int, height: int) -> None:
    self.width = width
    self.height = height

  @abc.abstractmethod
  def generate(self) -> list[list[bool]]:
    """Generate a boolean grid where True represents an obstacle/wall.

    Returns:
        A 2D list of booleans [width][height].
    """
    pass


class RandomObstacleGenerator(MapGenerator):
  """Legacy random obstacle generator."""

  def __init__(self, width: int, height: int, obstacle_count: int | None = None) -> None:
    super().__init__(width, height)
    self.obstacle_count = obstacle_count

  def generate(self) -> list[list[bool]]:
    obstacles = [[False for _ in range(self.height)] for _ in range(self.width)]

    count = self.obstacle_count
    if count is None:
      count = random.randint(3, 8)

    for _ in range(count):
      x = random.randrange(self.width)
      y = random.randrange(self.height)
      obstacles[x][y] = True

    return obstacles


class MazeGenerator(MapGenerator):
  """Generates a maze-like environment using Recursive Backtracking."""

  def generate(self) -> list[list[bool]]:
    # Initialize with all walls
    # Note: We use a grid where cells are at odd coordinates (1, 3, 5...)
    # and walls are at even coordinates or between cells.
    obstacles = [[True for _ in range(self.height)] for _ in range(self.width)]

    start_x = 1
    start_y = 1

    # Ensure start is within bounds
    if start_x >= self.width or start_y >= self.height:
        return [[False for _ in range(self.height)] for _ in range(self.width)]

    obstacles[start_x][start_y] = False
    stack = [(start_x, start_y)]

    while stack:
      current_x, current_y = stack[-1]
      neighbors = []

      # Check neighbors (jump 2 cells to leave room for walls)
      for dx, dy in [(0, -2), (0, 2), (-2, 0), (2, 0)]:
        nx, ny = current_x + dx, current_y + dy
        if 0 < nx < self.width - 1 and 0 < ny < self.height - 1:
          if obstacles[nx][ny]: # If unvisited (still a wall)
            neighbors.append((nx, ny, dx // 2, dy // 2))

      if neighbors:
        nx, ny, wx, wy = random.choice(neighbors)
        obstacles[nx][ny] = False # Carve cell
        obstacles[current_x + wx][current_y + wy] = False # Carve wall between
        stack.append((nx, ny))
      else:
        stack.pop()

    return obstacles


class RoomGenerator(MapGenerator):
  """Generates an office-like layout with rooms and corridors."""

  def generate(self) -> list[list[bool]]:
    obstacles = [[True for _ in range(self.height)] for _ in range(self.width)]

    # Create rooms
    rooms = []
    attempts = 0
    max_rooms = (self.width * self.height) // 50

    while len(rooms) < max_rooms and attempts < 100:
      attempts += 1
      w = random.randint(3, 6)
      h = random.randint(3, 6)
      x = random.randint(1, self.width - w - 1)
      y = random.randint(1, self.height - h - 1)

      new_room = (x, y, w, h)

      # Check overlap
      overlap = False
      for rx, ry, rw, rh in rooms:
        if (x < rx + rw + 1 and x + w + 1 > rx and
            y < ry + rh + 1 and y + h + 1 > ry):
          overlap = True
          break

      if not overlap:
        rooms.append(new_room)
        # Carve room
        for i in range(x, x + w):
          for j in range(y, y + h):
            obstacles[i][j] = False

    # Connect rooms with corridors
    for i in range(len(rooms) - 1):
      x1, y1, w1, h1 = rooms[i]
      x2, y2, w2, h2 = rooms[i+1]

      # Center points
      cx1, cy1 = x1 + w1 // 2, y1 + h1 // 2
      cx2, cy2 = x2 + w2 // 2, y2 + h2 // 2

      # Horizontal corridor
      start_x, end_x = min(cx1, cx2), max(cx1, cx2)
      for x in range(start_x, end_x + 1):
        obstacles[x][cy1] = False

      # Vertical corridor
      start_y, end_y = min(cy1, cy2), max(cy1, cy2)
      for y in range(start_y, end_y + 1):
        obstacles[cx2][y] = False

    return obstacles


class CellularAutomataGenerator(MapGenerator):
  """Generates cave-like natural terrain."""

  def generate(self) -> list[list[bool]]:
    # Initial random fill
    obstacles = [[random.random() < 0.45 for _ in range(self.height)] for _ in range(self.width)]

    # Simulation steps
    for _ in range(4):
      new_obstacles = [[False for _ in range(self.height)] for _ in range(self.width)]
      for x in range(self.width):
        for y in range(self.height):
          neighbors = 0
          for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
              if dx == 0 and dy == 0:
                continue
              nx, ny = x + dx, y + dy
              if nx < 0 or nx >= self.width or ny < 0 or ny >= self.height:
                neighbors += 1 # Edge counts as wall
              elif obstacles[nx][ny]:
                neighbors += 1

          if obstacles[x][y]:
            new_obstacles[x][y] = neighbors >= 4
          else:
            new_obstacles[x][y] = neighbors >= 5
      obstacles = new_obstacles

    return obstacles


MapType = Literal["random", "maze", "room", "cave"]

def create_generator(map_type: MapType, width: int, height: int, **kwargs) -> MapGenerator:
  if map_type == "maze":
    return MazeGenerator(width, height)
  elif map_type == "room":
    return RoomGenerator(width, height)
  elif map_type == "cave":
    return CellularAutomataGenerator(width, height)
  else:
    return RandomObstacleGenerator(width, height, **kwargs)
