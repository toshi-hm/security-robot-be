"""Map generation strategies for security environments."""

from __future__ import annotations

import abc
import random
from typing import Any, Literal

# -----------------------------------------------------------------------------
# Grid Indexing Convention:
#   - Format: grid[y][x] (row-major)
#   - y: row index (0 to height-1)
#   - x: col index (0 to width-1)
#   - Access: grid[y][x]
# -----------------------------------------------------------------------------


class MapGenerator(abc.ABC):
  """Abstract base class for map generation strategies."""

  def __init__(self, width: int, height: int, seed: int | None = None) -> None:
    self.width = width
    self.height = height
    self.rng = random.Random(seed)

  @abc.abstractmethod
  def generate(self) -> list[list[bool]]:
    """Generate a boolean grid where True represents an obstacle/wall.

    Returns:
        A 2D list of booleans [y][x] (row-major order: height rows, width columns).
    """
    pass

  def _is_connected(self, obstacles: list[list[bool]]) -> bool:
    """Check if all passable cells are connected using flood-fill.

    Args:
        obstacles: 2D grid where True = obstacle, False = passable.

    Returns:
        True if all passable cells form a single connected component.
    """
    # Find first passable cell
    start = None
    for y in range(self.height):
      for x in range(self.width):
        if not obstacles[y][x]:
          start = (x, y)
          break
      if start:
        break

    if not start:
      return False  # No passable cells

    # Flood-fill from start
    visited = set()
    stack = [start]
    while stack:
      x, y = stack.pop()
      if (x, y) in visited:
        continue
      visited.add((x, y))

      for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
        nx, ny = x + dx, y + dy
        if 0 <= nx < self.width and 0 <= ny < self.height:
          if not obstacles[ny][nx] and (nx, ny) not in visited:
            stack.append((nx, ny))

    # Count total passable cells
    total_passable = sum(sum(1 for cell in row if not cell) for row in obstacles)
    return len(visited) == total_passable

  def _force_connectivity(self, obstacles: list[list[bool]]) -> None:
    """Force connectivity by opening paths between isolated regions."""
    # Find all connected components
    visited = [[False for _ in range(self.width)] for _ in range(self.height)]
    components = []

    for y in range(self.height):
      for x in range(self.width):
        if not obstacles[y][x] and not visited[y][x]:
          # Found a new component, flood-fill it
          component = []
          stack = [(x, y)]
          while stack:
            cx, cy = stack.pop()
            if visited[cy][cx]:
              continue
            visited[cy][cx] = True
            component.append((cx, cy))

            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
              nx, ny = cx + dx, cy + dy
              if 0 <= nx < self.width and 0 <= ny < self.height:
                if not obstacles[ny][nx] and not visited[ny][nx]:
                  stack.append((nx, ny))

          components.append(component)

    # Connect components using MST (Prim's algorithm) to minimize path length
    if len(components) <= 1:
      return  # Already connected

    # Find largest component
    largest_idx = max(range(len(components)), key=lambda i: len(components[i]))

    # Calculate distances between components
    # For each component, find minimum distance to the connected set
    # Distances to the connected set: (distance, target_component_index)
    # Initialize with distance to the largest component
    min_dists = {}
    lx, ly = components[largest_idx][0]

    for i in range(len(components)):
      if i == largest_idx:
        continue
      cx, cy = components[i][0]
      dist = abs(cx - lx) + abs(cy - ly)
      min_dists[i] = (dist, largest_idx)

    while min_dists:
      # Find the closest unconnected component
      next_idx = min(min_dists, key=lambda k: min_dists[k][0])
      dist, parent_idx = min_dists[next_idx]

      # Connect next_idx to parent_idx
      x1, y1 = components[next_idx][0]
      x2, y2 = components[parent_idx][0]

      # Open a path between them (Horizontal then vertical)
      for x in range(min(x1, x2), max(x1, x2) + 1):
        obstacles[y1][x] = False
      for y in range(min(y1, y2), max(y1, y2) + 1):
        obstacles[y][x2] = False

      # Mark as connected (remove from min_dists)
      del min_dists[next_idx]

      # Update distances for remaining unconnected components
      nx, ny = components[next_idx][0]
      for i in min_dists:
        cx, cy = components[i][0]
        new_dist = abs(cx - nx) + abs(cy - ny)
        if new_dist < min_dists[i][0]:
          min_dists[i] = (new_dist, next_idx)


class RandomObstacleGenerator(MapGenerator):
  """Legacy random obstacle generator."""

  def __init__(
    self, width: int, height: int, seed: int | None = None, count: int | None = None
  ) -> None:
    super().__init__(width, height, seed)
    self.count = count

  def generate(self) -> list[list[bool]]:
    """Generate a random obstacle map with guaranteed connectivity."""
    max_retries = 10
    for _attempt in range(max_retries):
      obstacles = self._generate_attempt()
      if self._is_connected(obstacles):
        return obstacles

    # Fallback: force connectivity if retries fail
    obstacles = self._generate_attempt()
    self._force_connectivity(obstacles)
    return obstacles

  def _generate_attempt(self) -> list[list[bool]]:
    """Single attempt at generating random obstacles."""
    obstacles = [[False for _ in range(self.width)] for _ in range(self.height)]

    count = self.count
    if count is None:
      count = self.rng.randint(3, 8)

    placed = 0
    attempts = 0
    max_attempts = count * 10  # Avoid infinite loop

    while placed < count and attempts < max_attempts:
      x = self.rng.randrange(self.width)
      y = self.rng.randrange(self.height)
      if not obstacles[y][x]:
        obstacles[y][x] = True
        placed += 1
      attempts += 1

    return obstacles


class MazeGenerator(MapGenerator):
  """Generates a maze-like environment using Recursive Backtracking."""

  def generate(self) -> list[list[bool]]:
    if self.width < 5 or self.height < 5:
      raise ValueError("Maze generator requires a grid of at least 5x5")

    # Initialize with all walls
    # Note: We use a grid where cells are at odd coordinates (1, 3, 5...)
    # and walls are at even coordinates or between cells.
    obstacles = [[True for _ in range(self.width)] for _ in range(self.height)]

    start_x = 1
    start_y = 1

    obstacles[start_y][start_x] = False
    stack = [(start_x, start_y)]

    while stack:
      current_x, current_y = stack[-1]
      neighbors = []

      # Check neighbors (jump 2 cells to leave room for walls)
      for dx, dy in [(0, -2), (0, 2), (-2, 0), (2, 0)]:
        nx, ny = current_x + dx, current_y + dy
        # Boundary cells are always walls in our maze algorithm
        # Valid traversable area is (1, 1) to (width-2, height-2)
        if 0 < nx < self.width - 1 and 0 < ny < self.height - 1:
          if obstacles[ny][nx]:  # If unvisited (still a wall)
            neighbors.append((nx, ny, dx // 2, dy // 2))

      if neighbors:
        nx, ny, wx, wy = self.rng.choice(neighbors)
        obstacles[ny][nx] = False  # Carve cell
        obstacles[current_y + wy][current_x + wx] = False  # Carve wall between
        stack.append((nx, ny))
      else:
        stack.pop()

    return obstacles


class RoomGenerator(MapGenerator):
  """Generates an office-like layout with rooms and corridors."""

  def generate(self) -> list[list[bool]]:
    """Generate a room-based map with guaranteed connectivity."""
    max_retries = 10
    for _attempt in range(max_retries):
      obstacles = self._generate_attempt()
      if self._is_connected(obstacles):
        return obstacles

    raise RuntimeError(f"Failed to generate connected room map after {max_retries} attempts")

  def _generate_attempt(self) -> list[list[bool]]:
    """Single attempt at generating a room-based map."""
    obstacles = [[True for _ in range(self.width)] for _ in range(self.height)]

    # Create rooms
    rooms: list[tuple[int, int, int, int]] = []
    attempts = 0
    max_rooms = (self.width * self.height) // 50

    while len(rooms) < max_rooms and attempts < 100:
      attempts += 1

      # Dynamic room size based on environment dimensions
      max_w = min(6, self.width - 2)
      max_h = min(6, self.height - 2)

      if max_w < 3 or max_h < 3:
        # Environment too small for rooms, just return empty or simple
        break

      w = self.rng.randint(3, max_w)
      h = self.rng.randint(3, max_h)

      # Check if room can fit within bounds
      if self.width - w - 1 < 1 or self.height - h - 1 < 1:
        break

      x = self.rng.randint(1, self.width - w - 1)
      y = self.rng.randint(1, self.height - h - 1)

      new_room = (x, y, w, h)

      # Check overlap with 1-cell buffer between rooms for corridors
      ROOM_BUFFER = 1
      overlap = False
      for rx, ry, rw, rh in rooms:
        if (
          x < rx + rw + ROOM_BUFFER
          and x + w + ROOM_BUFFER > rx
          and y < ry + rh + ROOM_BUFFER
          and y + h + ROOM_BUFFER > ry
        ):
          overlap = True
          break

      if not overlap:
        rooms.append(new_room)
        # Carve room
        for i in range(x, x + w):
          for j in range(y, y + h):
            obstacles[j][i] = False

    # Connect rooms using nearest-neighbor to ensure full connectivity
    for i, (x1, y1, w1, h1) in enumerate(rooms):
      if i == 0:
        continue

      # Find nearest existing room
      min_dist = float("inf")
      nearest_idx = 0
      cx1 = x1 + w1 // 2
      cy1 = y1 + h1 // 2

      for j in range(i):
        x2, y2, w2, h2 = rooms[j]
        cx2 = x2 + w2 // 2
        cy2 = y2 + h2 // 2
        dist = abs(cx1 - cx2) + abs(cy1 - cy2)
        if dist < min_dist:
          min_dist = dist
          nearest_idx = j

      # Connect to nearest room
      x2, y2, w2, h2 = rooms[nearest_idx]
      cx2 = x2 + w2 // 2
      cy2 = y2 + h2 // 2

      # Horizontal corridor
      start_x, end_x = min(cx1, cx2), max(cx1, cx2)
      for x in range(start_x, end_x + 1):
        obstacles[cy1][x] = False

      # Vertical corridor
      start_y, end_y = min(cy1, cy2), max(cy1, cy2)
      for y in range(start_y, end_y + 1):
        obstacles[y][cx2] = False

    # Ensure at least one room exists if generation failed
    if not rooms:
      # Create a fallback room in the center
      w = min(4, self.width - 2)
      h = min(4, self.height - 2)

      if w < 1 or h < 1:
        raise ValueError(f"Grid size {self.width}x{self.height} too small for RoomGenerator")

      x = (self.width - w) // 2
      y = (self.height - h) // 2

      for i in range(x, x + w):
        for j in range(y, y + h):
          obstacles[j][i] = False

    if not self._is_connected(obstacles):
      # Should not happen with fallback, but safety check
      raise RuntimeError("RoomGenerator failed to generate connected map")

    return obstacles


class CellularAutomataGenerator(MapGenerator):
  """Generates cave-like natural terrain."""

  def __init__(
    self, width: int, height: int, seed: int | None = None, initial_wall_probability: float = 0.45
  ) -> None:
    super().__init__(width, height, seed)
    self.initial_wall_probability = initial_wall_probability

  def generate(self) -> list[list[bool]]:
    """Generate a cave-like map with guaranteed connectivity."""
    max_retries = 10
    for _attempt in range(max_retries):
      obstacles = self._generate_attempt()
      if self._is_connected(obstacles):
        return obstacles

    # Fallback: force connectivity if retries fail
    obstacles = self._generate_attempt()
    self._force_connectivity(obstacles)
    return obstacles

  def _generate_attempt(self) -> list[list[bool]]:
    """Single attempt at generating a cave using cellular automata."""
    # Initial random fill
    obstacles = [
      [self.rng.random() < self.initial_wall_probability for _ in range(self.width)]
      for _ in range(self.height)
    ]

    # Simulation steps
    for _ in range(4):
      new_obstacles = [[False for _ in range(self.width)] for _ in range(self.height)]
      for y in range(self.height):
        for x in range(self.width):
          neighbors = 0
          for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
              if dx == 0 and dy == 0:
                continue
              nx, ny = x + dx, y + dy
              if nx < 0 or nx >= self.width or ny < 0 or ny >= self.height:
                neighbors += 1  # Edge counts as wall
              elif obstacles[ny][nx]:
                neighbors += 1

          if obstacles[y][x]:
            new_obstacles[y][x] = neighbors >= 4
          else:
            new_obstacles[y][x] = neighbors >= 5
      obstacles = new_obstacles

    return obstacles


MapType = Literal["random", "maze", "room", "cave"]


def create_generator(
  map_type: MapType, width: int, height: int, seed: int | None = None, **kwargs: Any
) -> MapGenerator:
  if map_type == "maze":
    return MazeGenerator(width, height, seed=seed)
  elif map_type == "room":
    return RoomGenerator(width, height, seed=seed)
  elif map_type == "cave":
    return CellularAutomataGenerator(width, height, seed=seed)
  else:
    return RandomObstacleGenerator(width, height, seed=seed, **kwargs)
