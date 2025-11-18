"""Unit tests for template-based patrol agents."""


from rl.agents.template_agents import (ACTION_MOVE_FORWARD, ACTION_PATROL,
                                       ACTION_TURN_LEFT, ACTION_TURN_RIGHT,
                                       DIRECTION_EAST, DIRECTION_NORTH,
                                       DIRECTION_SOUTH, DIRECTION_WEST,
                                       HorizontalScanAgent, RandomWalkAgent,
                                       SpiralAgent, VerticalScanAgent)


class TestHorizontalScanAgent:
    """Tests for horizontal scan patrol pattern."""

    def test_path_generation_small_grid(self) -> None:
        """Test path generation for a small 3x3 grid."""
        agent = HorizontalScanAgent(3, 3)

        expected_path = [
            # Row 0: left to right
            (0, 0),
            (1, 0),
            (2, 0),
            # Row 1: right to left
            (2, 1),
            (1, 1),
            (0, 1),
            # Row 2: left to right
            (0, 2),
            (1, 2),
            (2, 2),
        ]

        assert agent.target_path == expected_path

    def test_path_generation_covers_all_cells(self) -> None:
        """Test that path covers all grid cells exactly once."""
        width, height = 5, 4
        agent = HorizontalScanAgent(width, height)

        # Check all cells are covered
        all_cells = {(x, y) for x in range(width) for y in range(height)}
        path_cells = set(agent.target_path)

        assert path_cells == all_cells
        assert len(agent.target_path) == width * height

    def test_zigzag_pattern(self) -> None:
        """Test that even rows go left-to-right and odd rows go right-to-left."""
        agent = HorizontalScanAgent(4, 3)

        # Extract row 0 (even - left to right)
        row_0 = [(x, y) for x, y in agent.target_path if y == 0]
        assert row_0 == [(0, 0), (1, 0), (2, 0), (3, 0)]

        # Extract row 1 (odd - right to left)
        row_1 = [(x, y) for x, y in agent.target_path if y == 1]
        assert row_1 == [(3, 1), (2, 1), (1, 1), (0, 1)]

        # Extract row 2 (even - left to right)
        row_2 = [(x, y) for x, y in agent.target_path if y == 2]
        assert row_2 == [(0, 2), (1, 2), (2, 2), (3, 2)]

    def test_get_action_at_target_returns_patrol(self) -> None:
        """Test that agent patrols when at target position."""
        agent = HorizontalScanAgent(3, 3)
        agent.current_path_index = 0

        # At target (0, 0)
        action = agent.get_action(0, 0, DIRECTION_EAST, set())

        assert action == ACTION_PATROL
        assert agent.current_path_index == 1

    def test_get_action_moves_towards_target(self) -> None:
        """Test that agent moves towards target position."""
        agent = HorizontalScanAgent(3, 3)
        agent.current_path_index = 1  # Target is (1, 0)

        # At (0, 0) facing east, should move forward
        action = agent.get_action(0, 0, DIRECTION_EAST, set())
        assert action == ACTION_MOVE_FORWARD

    def test_get_action_turns_to_face_target(self) -> None:
        """Test that agent turns to face target when not aligned."""
        agent = HorizontalScanAgent(3, 3)
        agent.current_path_index = 1  # Target is (1, 0)

        # At (0, 0) facing north, should turn to face east
        action = agent.get_action(0, 0, DIRECTION_NORTH, set())
        assert action == ACTION_TURN_RIGHT

    def test_path_cycles_after_completion(self) -> None:
        """Test that path cycles back to beginning after completion."""
        agent = HorizontalScanAgent(2, 2)
        agent.current_path_index = len(agent.target_path)  # Beyond end

        # Should reset to 0
        _action = agent.get_action(0, 0, DIRECTION_EAST, set())
        assert agent.current_path_index in [0, 1]

    def test_reset_resets_path_index(self) -> None:
        """Test that reset() resets path index to 0."""
        agent = HorizontalScanAgent(3, 3)
        agent.current_path_index = 5

        agent.reset()

        assert agent.current_path_index == 0


class TestSpiralAgent:
    """Tests for spiral patrol pattern."""

    def test_path_generation_small_grid(self) -> None:
        """Test path generation for a 3x3 grid."""
        agent = SpiralAgent(3, 3)

        expected_path = [
            # Top edge: left to right
            (0, 0),
            (1, 0),
            (2, 0),
            # Right edge: top to bottom
            (2, 1),
            (2, 2),
            # Bottom edge: right to left
            (1, 2),
            (0, 2),
            # Left edge: bottom to top
            (0, 1),
            # Center
            (1, 1),
        ]

        assert agent.target_path == expected_path

    def test_path_generation_4x4_grid(self) -> None:
        """Test path generation for a 4x4 grid."""
        agent = SpiralAgent(4, 4)

        # First layer (outer)
        outer = agent.target_path[:12]
        expected_outer = [
            (0, 0),
            (1, 0),
            (2, 0),
            (3, 0),  # Top
            (3, 1),
            (3, 2),
            (3, 3),  # Right
            (2, 3),
            (1, 3),
            (0, 3),  # Bottom
            (0, 2),
            (0, 1),  # Left
        ]
        assert outer == expected_outer

        # Inner layer
        inner = agent.target_path[12:]
        expected_inner = [(1, 1), (2, 1), (2, 2), (1, 2)]
        assert inner == expected_inner

    def test_path_covers_all_cells(self) -> None:
        """Test that spiral path covers all cells exactly once."""
        width, height = 5, 4
        agent = SpiralAgent(width, height)

        all_cells = {(x, y) for x in range(width) for y in range(height)}
        path_cells = set(agent.target_path)

        assert path_cells == all_cells
        assert len(agent.target_path) == width * height

    def test_clockwise_direction(self) -> None:
        """Test that spiral moves clockwise."""
        agent = SpiralAgent(5, 5)

        # First few steps should be: right, down, left, up (clockwise)
        # Starting at (0,0), going right to (4,0)
        assert agent.target_path[0] == (0, 0)
        assert agent.target_path[4] == (4, 0)

        # Then down from (4,0) to (4,4)
        assert agent.target_path[5] == (4, 1)
        assert agent.target_path[8] == (4, 4)

        # Then left from (4,4) to (0,4)
        assert agent.target_path[9] == (3, 4)
        assert agent.target_path[12] == (0, 4)

    def test_single_cell_grid(self) -> None:
        """Test spiral for 1x1 grid."""
        agent = SpiralAgent(1, 1)
        assert agent.target_path == [(0, 0)]

    def test_rectangular_grid(self) -> None:
        """Test spiral for non-square grid."""
        agent = SpiralAgent(3, 2)

        expected_path = [
            (0, 0),
            (1, 0),
            (2, 0),  # Top
            (2, 1),  # Right
            (1, 1),
            (0, 1),  # Bottom
        ]

        assert agent.target_path == expected_path
        assert len(agent.target_path) == 6


class TestVerticalScanAgent:
    """Tests for vertical scan patrol pattern."""

    def test_path_generation_small_grid(self) -> None:
        """Test path generation for a 3x3 grid."""
        agent = VerticalScanAgent(3, 3)

        expected_path = [
            # Column 0: top to bottom
            (0, 0),
            (0, 1),
            (0, 2),
            # Column 1: bottom to top
            (1, 2),
            (1, 1),
            (1, 0),
            # Column 2: top to bottom
            (2, 0),
            (2, 1),
            (2, 2),
        ]

        assert agent.target_path == expected_path

    def test_path_covers_all_cells(self) -> None:
        """Test that vertical scan covers all cells."""
        width, height = 4, 5
        agent = VerticalScanAgent(width, height)

        all_cells = {(x, y) for x in range(width) for y in range(height)}
        path_cells = set(agent.target_path)

        assert path_cells == all_cells


class TestRandomWalkAgent:
    """Tests for random walk patrol pattern."""

    def test_initialization(self) -> None:
        """Test that random walk agent initializes correctly."""
        agent = RandomWalkAgent(5, 5, seed=42)
        assert agent.width == 5
        assert agent.height == 5
        assert agent.target_path == []

    def test_get_action_returns_valid_action(self) -> None:
        """Test that random walk returns valid actions."""
        agent = RandomWalkAgent(5, 5, seed=42)

        for _ in range(100):
            action = agent.get_action(2, 2, DIRECTION_NORTH, set())
            assert action in [
                ACTION_MOVE_FORWARD,
                ACTION_TURN_LEFT,
                ACTION_TURN_RIGHT,
                ACTION_PATROL,
            ]

    def test_reproducibility_with_seed(self) -> None:
        """Test that same seed produces same actions."""
        agent1 = RandomWalkAgent(5, 5, seed=123)
        agent2 = RandomWalkAgent(5, 5, seed=123)

        actions1 = [agent1.get_action(2, 2, DIRECTION_NORTH, set()) for _ in range(10)]
        actions2 = [agent2.get_action(2, 2, DIRECTION_NORTH, set()) for _ in range(10)]

        assert actions1 == actions2

    def test_different_seeds_produce_different_actions(self) -> None:
        """Test that different seeds produce different actions."""
        agent1 = RandomWalkAgent(5, 5, seed=100)
        agent2 = RandomWalkAgent(5, 5, seed=200)

        actions1 = [agent1.get_action(2, 2, DIRECTION_NORTH, set()) for _ in range(20)]
        actions2 = [agent2.get_action(2, 2, DIRECTION_NORTH, set()) for _ in range(20)]

        # Very unlikely to be the same with different seeds
        assert actions1 != actions2


class TestNavigationLogic:
    """Tests for common navigation logic."""

    def test_turn_left_from_north(self) -> None:
        """Test turning left from north direction."""
        agent = HorizontalScanAgent(3, 3)

        # Current: North (0), Target: West (3)
        # diff = (3 - 0) % 4 = 3, should turn left
        action = agent._get_turn_action(DIRECTION_NORTH, DIRECTION_WEST)
        assert action == ACTION_TURN_LEFT

    def test_turn_right_from_north(self) -> None:
        """Test turning right from north direction."""
        agent = HorizontalScanAgent(3, 3)

        # Current: North (0), Target: East (1)
        # diff = (1 - 0) % 4 = 1, should turn right
        action = agent._get_turn_action(DIRECTION_NORTH, DIRECTION_EAST)
        assert action == ACTION_TURN_RIGHT

    def test_turn_180_degrees(self) -> None:
        """Test turning 180 degrees."""
        agent = HorizontalScanAgent(3, 3)

        # Current: North (0), Target: South (2)
        # diff = (2 - 0) % 4 = 2, should turn right
        action = agent._get_turn_action(DIRECTION_NORTH, DIRECTION_SOUTH)
        assert action == ACTION_TURN_RIGHT

    def test_avoid_obstacle(self) -> None:
        """Test that agent avoids obstacles."""
        agent = HorizontalScanAgent(3, 3)
        agent.current_path_index = 1  # Target is (1, 0)

        obstacles = {(1, 0)}  # Obstacle at target

        # At (0, 0) facing east, but (1, 0) is blocked
        # Should turn right to find alternative path
        action = agent.get_action(0, 0, DIRECTION_EAST, obstacles)
        assert action == ACTION_TURN_RIGHT

    def test_valid_position_check(self) -> None:
        """Test position validity checking."""
        agent = HorizontalScanAgent(5, 5)

        # Valid positions
        assert agent._is_valid_position(0, 0) is True
        assert agent._is_valid_position(4, 4) is True
        assert agent._is_valid_position(2, 3) is True

        # Invalid positions
        assert agent._is_valid_position(-1, 0) is False
        assert agent._is_valid_position(0, -1) is False
        assert agent._is_valid_position(5, 0) is False
        assert agent._is_valid_position(0, 5) is False

    def test_get_front_position(self) -> None:
        """Test getting front position based on direction."""
        agent = HorizontalScanAgent(5, 5)

        # North: dy = -1
        assert agent._get_front_position(2, 2, DIRECTION_NORTH) == (2, 1)

        # East: dx = +1
        assert agent._get_front_position(2, 2, DIRECTION_EAST) == (3, 2)

        # South: dy = +1
        assert agent._get_front_position(2, 2, DIRECTION_SOUTH) == (2, 3)

        # West: dx = -1
        assert agent._get_front_position(2, 2, DIRECTION_WEST) == (1, 2)

    def test_desired_direction_prioritizes_horizontal(self) -> None:
        """Test that horizontal movement is prioritized."""
        agent = HorizontalScanAgent(5, 5)

        # dx > 0 should return EAST
        assert agent._get_desired_direction(2, 1) == DIRECTION_EAST
        assert agent._get_desired_direction(2, -1) == DIRECTION_EAST

        # dx < 0 should return WEST
        assert agent._get_desired_direction(-2, 1) == DIRECTION_WEST
        assert agent._get_desired_direction(-2, -1) == DIRECTION_WEST

        # dx = 0, dy > 0 should return SOUTH
        assert agent._get_desired_direction(0, 2) == DIRECTION_SOUTH

        # dx = 0, dy < 0 should return NORTH
        assert agent._get_desired_direction(0, -2) == DIRECTION_NORTH
