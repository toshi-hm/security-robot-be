
import unittest
import numpy as np
from rl.environments.security_env import SecurityEnvironment

class TestCollisionLogic(unittest.TestCase):
    def setUp(self):
        # Setup a simple environment
        self.env = SecurityEnvironment(width=10, height=10, num_robots=3)
        # Reset to clear state
        self.env.reset()

    def test_vertex_collision_3_robots(self):
        """Test 3 robots trying to move to the same cell."""
        # Arrange
        # Robots at (0,0), (1,0), (0,1)
        self.env.robot_positions = [(0, 0), (1, 0), (0, 1)]
        self.env.battery_levels = [100.0] * 3
        
        # All try to move to (0,0) or (1,1)?
        # Let's say they all try to move to (0,0).
        # Robot 0 stays at (0,0). Robot 1 moves Left to (0,0). Robot 2 moves Up (assuming y=0 is top) to (0,0)?
        # Directions: 0: Front, 1: Left, 2: Right, 3: Patrol
        # We need to set directions so 'Front' leads to the target.
        
        # Target (1, 1)
        # Robot 0 at (1, 0), facing South (0, 1) -> moves to (1, 1)
        # Robot 1 at (0, 1), facing East (1, 0) -> moves to (1, 1)
        # Robot 2 at (2, 1), facing West (-1, 0) -> moves to (1, 1)
        
        # Directions: 0: (0, -1) [North], 1: (1, 0) [East], 2: (0, 1) [South], 3: (-1, 0) [West]
        # Wait, let's check _get_front_position logic in security_env.py
        # dx, dy = [(0, -1), (1, 0), (0, 1), (-1, 0)][self.robot_directions[robot_idx]]
        # So: 0=North, 1=East, 2=South, 3=West
        
        self.env.robot_positions = [(1, 0), (0, 1), (2, 1)]
        self.env.robot_directions = [2, 1, 3] # South, East, West
        
        # Act
        # All move forward (Action 0)
        proposed_positions = []
        for i in range(3):
            proposed_positions.append(self.env._get_front_position(i))
            
        # Verify proposed positions are all (1, 1)
        self.assertEqual(proposed_positions, [(1, 1), (1, 1), (1, 1)])
        
        # Resolve collisions
        final_positions, penalty = self.env._resolve_collisions(proposed_positions)
        
        # Assert
        # All should fail to move and stay at original positions
        self.assertEqual(final_positions, self.env.robot_positions)
        # Penalty should be applied
        # 3 robots collision: -0.5 * 3 * (1.0 + (3-2)*0.3) = -1.5 * 1.3 = -1.95
        expected_penalty = -0.5 * 3 * 1.3
        self.assertAlmostEqual(penalty, expected_penalty)

    def test_swap_collision(self):
        """Test 2 robots swapping positions."""
        # Arrange
        self.env.num_robots = 2
        self.env.robot_positions = [(0, 0), (0, 1)]
        self.env.battery_levels = [100.0] * 2
        
        # Robot 0 at (0,0) facing South (2) -> moves to (0,1)
        # Robot 1 at (0,1) facing North (0) -> moves to (0,0)
        self.env.robot_directions = [2, 0]
        
        proposed_positions = [(0, 1), (0, 0)]
        
        # Act
        final_positions, penalty = self.env._resolve_collisions(proposed_positions)
        
        # Assert
        # Should stay in place
        self.assertEqual(final_positions, self.env.robot_positions)
        # Penalty: -0.5 per robot involved in swap?
        # Code: if self._is_swap(...): penalty -= self.COLLISION_BASE_PENALTY
        # This is called for EACH robot in the swap. So total penalty = -0.5 * 2 = -1.0
        self.assertEqual(penalty, -1.0)

    def test_corner_collision(self):
        """Test collision in a corner."""
        # Arrange
        self.env.num_robots = 2
        # Corner (0,0)
        # Robot 0 at (1, 0) facing West (3) -> (0, 0)
        # Robot 1 at (0, 1) facing North (0) -> (0, 0)
        self.env.robot_positions = [(1, 0), (0, 1)]
        self.env.robot_directions = [3, 0]
        self.env.battery_levels = [100.0] * 2
        
        proposed_positions = [(0, 0), (0, 0)]
        
        # Act
        final_positions, penalty = self.env._resolve_collisions(proposed_positions)
        
        # Assert
        self.assertEqual(final_positions, self.env.robot_positions)
        # Penalty: 2 robots -> -0.5 * 2 * 1.0 = -1.0
        self.assertEqual(penalty, -1.0)

    def test_no_collision(self):
        """Test valid moves with no collision."""
        # Arrange
        self.env.num_robots = 2
        self.env.robot_positions = [(0, 0), (0, 2)]
        self.env.robot_directions = [2, 2] # Both South
        self.env.battery_levels = [100.0] * 2
        
        proposed_positions = [(0, 1), (0, 3)]
        
        # Act
        final_positions, penalty = self.env._resolve_collisions(proposed_positions)
        
        # Assert
        self.assertEqual(final_positions, proposed_positions)
        self.assertEqual(penalty, 0.0)

if __name__ == '__main__':
    unittest.main()
