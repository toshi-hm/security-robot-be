"""
Template-based patrol agents for comparison with RL agents.

These agents follow predetermined patrol patterns and serve as baselines
for evaluating reinforcement learning approaches.
"""

from abc import ABC, abstractmethod

import numpy as np

# Action constants matching SecurityEnvironment
ACTION_MOVE_FORWARD = 0
ACTION_TURN_LEFT = 1
ACTION_TURN_RIGHT = 2
ACTION_PATROL = 3

# Direction constants (robot_direction values)
DIRECTION_NORTH = 0  # up (dy=-1)
DIRECTION_EAST = 1  # right (dx=+1)
DIRECTION_SOUTH = 2  # down (dy=+1)
DIRECTION_WEST = 3  # left (dx=-1)


class BaseTemplateAgent(ABC):
  """Abstract base class for template-based patrol agents."""

  def __init__(self, width: int, height: int) -> None:
    """
    Initialize the template agent.

    Args:
        width: Grid width
        height: Grid height
    """
    self.width = width
    self.height = height
    self.target_path: list[tuple[int, int]] = []
    self.current_path_index = 0
    self.generate_patrol_path()

  @abstractmethod
  def generate_patrol_path(self) -> None:
    """Generate the patrol path for this pattern."""

  def reset(self) -> None:
    """Reset the agent to start from the beginning of the pattern."""
    self.current_path_index = 0

  def get_action(self, robot_x: int, robot_y: int, robot_direction: int, obstacles: set) -> int:
    """
    Get the next action to move towards the target position.

    Args:
        robot_x: Current robot X position
        robot_y: Current robot Y position
        robot_direction: Current robot direction (0=N, 1=E, 2=S, 3=W)
        obstacles: Set of obstacle positions

    Returns:
        Action to take (0=forward, 1=left, 2=right, 3=patrol)
    """
    if self.current_path_index >= len(self.target_path):
      # Cycle back to the beginning
      self.current_path_index = 0

    target_x, target_y = self.target_path[self.current_path_index]

    # If already at target, patrol and move to next target
    if robot_x == target_x and robot_y == target_y:
      self.current_path_index += 1
      return ACTION_PATROL

    # Calculate direction to target
    action = self._navigate_to_target(
      robot_x, robot_y, robot_direction, target_x, target_y, obstacles
    )
    return action

  def _navigate_to_target(
    self,
    robot_x: int,
    robot_y: int,
    robot_direction: int,
    target_x: int,
    target_y: int,
    obstacles: set,
  ) -> int:
    """
    Navigate towards the target position using BFS for obstacle avoidance.

    Args:
        robot_x: Current robot X position
        robot_y: Current robot Y position
        robot_direction: Current robot direction
        target_x: Target X position
        target_y: Target Y position
        obstacles: Set of obstacle positions

    Returns:
        Action to take
    """
    # Calculate direction vectors
    dx = target_x - robot_x
    dy = target_y - robot_y

    # Determine desired direction
    desired_direction = self._get_desired_direction(dx, dy)

    # If facing the wrong direction, turn
    if robot_direction != desired_direction:
      return self._get_turn_action(robot_direction, desired_direction)

    # Check if forward position is valid
    front_x, front_y = self._get_front_position(robot_x, robot_y, robot_direction)
    if self._is_valid_position(front_x, front_y) and (front_x, front_y) not in obstacles:
      return ACTION_MOVE_FORWARD

    # If blocked, use BFS to find alternative path
    next_pos = self._bfs_next_step(robot_x, robot_y, target_x, target_y, obstacles)
    if next_pos:
      next_x, next_y = next_pos
      # Calculate direction to next step
      step_dx = next_x - robot_x
      step_dy = next_y - robot_y
      desired_dir = self._get_desired_direction(step_dx, step_dy)
      if robot_direction != desired_dir:
        return self._get_turn_action(robot_direction, desired_dir)
      return ACTION_MOVE_FORWARD

    # If no path found, turn right as fallback
    return ACTION_TURN_RIGHT

  def _bfs_next_step(
    self,
    start_x: int,
    start_y: int,
    goal_x: int,
    goal_y: int,
    obstacles: set,
  ) -> tuple[int, int] | None:
    """
    Use BFS to find the next step towards the goal avoiding obstacles.

    Args:
        start_x: Current X position
        start_y: Current Y position
        goal_x: Goal X position
        goal_y: Goal Y position
        obstacles: Set of obstacle positions

    Returns:
        Next position (x, y) to move to, or None if no path exists
    """
    from collections import deque

    if start_x == goal_x and start_y == goal_y:
      return None

    # BFS queue: (x, y, path)
    queue = deque([(start_x, start_y, [])])
    visited = {(start_x, start_y)}

    # Direction vectors: N, E, S, W
    directions = [(0, -1), (1, 0), (0, 1), (-1, 0)]

    while queue:
      x, y, path = queue.popleft()

      for dx_dir, dy_dir in directions:
        nx, ny = x + dx_dir, y + dy_dir

        if not self._is_valid_position(nx, ny):
          continue
        if (nx, ny) in obstacles:
          continue
        if (nx, ny) in visited:
          continue

        new_path = path + [(nx, ny)]

        # Found the goal
        if nx == goal_x and ny == goal_y:
          return new_path[0] if new_path else None

        visited.add((nx, ny))
        queue.append((nx, ny, new_path))

    # No path found
    return None

  def _get_desired_direction(self, dx: int, dy: int) -> int:
    """
    Get the desired direction to move towards target.

    Prioritizes horizontal movement for scan pattern.

    Args:
        dx: X difference to target
        dy: Y difference to target

    Returns:
        Desired direction (0=N, 1=E, 2=S, 3=W)
    """
    # Prioritize horizontal movement for scan pattern
    if dx > 0:
      return DIRECTION_EAST
    elif dx < 0:
      return DIRECTION_WEST
    elif dy > 0:
      return DIRECTION_SOUTH
    elif dy < 0:
      return DIRECTION_NORTH
    else:
      return DIRECTION_NORTH  # Default

  def _get_turn_action(self, current_direction: int, desired_direction: int) -> int:
    """
    Get the turn action to change from current to desired direction.

    Args:
        current_direction: Current robot direction
        desired_direction: Desired robot direction

    Returns:
        Turn action (ACTION_TURN_LEFT or ACTION_TURN_RIGHT)
    """
    # Calculate turn difference
    diff = (desired_direction - current_direction) % 4

    if diff == 1 or diff == 2:
      return ACTION_TURN_RIGHT
    else:
      return ACTION_TURN_LEFT

  def _get_front_position(
    self, robot_x: int, robot_y: int, robot_direction: int
  ) -> tuple[int, int]:
    """
    Get the position in front of the robot.

    Args:
        robot_x: Current robot X position
        robot_y: Current robot Y position
        robot_direction: Current robot direction

    Returns:
        Front position (x, y)
    """
    dx, dy = [(0, -1), (1, 0), (0, 1), (-1, 0)][robot_direction]
    return robot_x + dx, robot_y + dy

  def _is_valid_position(self, x: int, y: int) -> bool:
    """
    Check if position is within grid bounds.

    Args:
        x: X position
        y: Y position

    Returns:
        True if valid, False otherwise
    """
    return 0 <= x < self.width and 0 <= y < self.height


class HorizontalScanAgent(BaseTemplateAgent):
  """
  Horizontal scan patrol pattern.

  Starts from top-left corner and scans horizontally row by row.
  After reaching the bottom, returns to the top and repeats.

  Pattern:
  → → → → →
  ← ← ← ← ←
  → → → → →
  ...
  """

  def generate_patrol_path(self) -> None:
    """Generate horizontal zigzag scan pattern."""
    self.target_path = []

    for y in range(self.height):
      if y % 2 == 0:
        # Left to right
        for x in range(self.width):
          self.target_path.append((x, y))
      else:
        # Right to left
        for x in range(self.width - 1, -1, -1):
          self.target_path.append((x, y))


class SpiralAgent(BaseTemplateAgent):
  """
  Spiral patrol pattern (clockwise from outside to inside).

  Starts from top-left corner and spirals inward clockwise.

  Pattern:
  → → → → ↓
  ↑       ↓
  ↑   ←   ↓
  ↑ ← ← ← ←
  """

  def generate_patrol_path(self) -> None:
    """Generate clockwise spiral pattern from outside to inside."""
    self.target_path = []

    # Track boundaries
    top = 0
    bottom = self.height - 1
    left = 0
    right = self.width - 1

    while top <= bottom and left <= right:
      # Move right along top edge
      for x in range(left, right + 1):
        self.target_path.append((x, top))
      top += 1

      # Move down along right edge
      for y in range(top, bottom + 1):
        self.target_path.append((right, y))
      right -= 1

      # Move left along bottom edge
      if top <= bottom:
        for x in range(right, left - 1, -1):
          self.target_path.append((x, bottom))
        bottom -= 1

      # Move up along left edge
      if left <= right:
        for y in range(bottom, top - 1, -1):
          self.target_path.append((left, y))
        left += 1


class VerticalScanAgent(BaseTemplateAgent):
  """
  Vertical scan patrol pattern.

  Starts from top-left corner and scans vertically column by column.

  Pattern:
  ↓ ↑ ↓ ↑
  ↓ ↑ ↓ ↑
  ↓ ↑ ↓ ↑
  ↓ ↑ ↓ ↑
  """

  def generate_patrol_path(self) -> None:
    """Generate vertical zigzag scan pattern."""
    self.target_path = []

    for x in range(self.width):
      if x % 2 == 0:
        # Top to bottom
        for y in range(self.height):
          self.target_path.append((x, y))
      else:
        # Bottom to top
        for y in range(self.height - 1, -1, -1):
          self.target_path.append((x, y))


class RandomWalkAgent(BaseTemplateAgent):
  """
  Random walk patrol pattern.

  Randomly selects next position from adjacent cells.
  This serves as a naive baseline.
  """

  def __init__(self, width: int, height: int, seed: int | None = None) -> None:
    """
    Initialize the random walk agent.

    Args:
        width: Grid width
        height: Grid height
        seed: Random seed for reproducibility
    """
    self.rng = np.random.default_rng(seed)
    super().__init__(width, height)

  def generate_patrol_path(self) -> None:
    """Random walk doesn't pre-generate a path."""
    self.target_path = []

  def reset(self) -> None:
    """Reset the agent."""
    pass

  def get_action(self, robot_x: int, robot_y: int, robot_direction: int, obstacles: set) -> int:
    """
    Get a random action.

    Args:
        robot_x: Current robot X position
        robot_y: Current robot Y position
        robot_direction: Current robot direction
        obstacles: Set of obstacle positions

    Returns:
        Random action
    """
    # 30% chance to patrol, otherwise move randomly
    if self.rng.random() < 0.3:
      return ACTION_PATROL

    # Try to move forward if possible
    front_x, front_y = self._get_front_position(robot_x, robot_y, robot_direction)
    if (
      self._is_valid_position(front_x, front_y)
      and (front_x, front_y) not in obstacles
      and self.rng.random() < 0.6
    ):
      return ACTION_MOVE_FORWARD

    # Otherwise turn randomly
    if self.rng.random() < 0.5:
      return ACTION_TURN_LEFT
    else:
      return ACTION_TURN_RIGHT
