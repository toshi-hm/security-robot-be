
import pytest
import numpy as np
from rl.environments.enhanced_env import EnhancedSecurityEnvironment

class TestEnhancedRewardComposition:
    def test_reward_composition(self):
        """Test that enhanced reward is composed of Base + Avg(PerRobot) + Global."""
        env = EnhancedSecurityEnvironment(
            width=10, height=10, num_robots=2,
            coverage_weight=1.0,
            exploration_weight=1.0,
            diversity_weight=1.0
        )
        env.reset()
        
        # Mock methods to return known values
        # We can't easily mock methods on the instance without a mocking library or subclassing.
        # But we can verify the formula by checking the result.
        
        # Let's make a step where we know what happens.
        # R0 moves to new cell -> Exploration +1.0, Movement +1.0
        # R1 moves to new cell -> Exploration +1.0, Movement +1.0
        # Coverage increases -> Global Coverage Reward > 0
        # Diversity -> Global Diversity Reward
        
        # It's hard to predict exact values.
        # Let's just check if Global Reward is NOT divided by N.
        
        # Case: 2 robots.
        # Suppose Global Reward is G.
        # Suppose Per-Robot Reward Sum is P.
        # Old Formula: (P + G) / 2 = P/2 + G/2
        # New Formula: P/2 + G
        
        # We can try to isolate G.
        # Set exploration_weight=0, movement_weight (implicit)=0? No, movement is hardcoded.
        
        # Let's use a subclass to control rewards.
        class MockEnv(EnhancedSecurityEnvironment):
            def _calculate_coverage_reward(self, ratio):
                return 10.0 # Global
            def _calculate_diversity_reward(self):
                return 5.0 # Global
            def _calculate_exploration_reward(self, idx):
                return 2.0 # Per Robot
            def _calculate_movement_reward(self, idx, action):
                return 0.0
            def _calculate_patrol_optimization_reward(self, idx, action):
                return 0.0
            def step(self, actions):
                # We need to call super().step() but we want to control base_reward too.
                # But we can't easily control base_reward without mocking SecurityEnv.
                # However, we know base_reward is small (movement/collision).
                # Let's just check the *difference* or the magnitude.
                return super().step(actions)

        mock_env = MockEnv(width=10, height=10, num_robots=2)
        mock_env.reset()
        
        actions = [0, 0]
        _, reward, _, _, info = mock_env.step(actions)
        
        # Expected Calculation:
        # Global = 10.0 + 5.0 = 15.0
        # Per Robot Sum = 2.0 * 2 = 4.0
        # Avg Per Robot = 4.0 / 2 = 2.0
        # Base Reward: Let's assume it's B.
        # Total = B + 2.0 + 15.0 = B + 17.0
        
        # If it was the old formula:
        # (B*2 + 4.0 + 15.0) / 2 = B + 2.0 + 7.5 = B + 9.5
        # (Assuming base reward was also normalized... wait. 
        # In old formula: enhanced = base + (per_robot + global)/N
        # base was already normalized.
        # So: B + (4.0 + 15.0)/2 = B + 9.5.
        
        # So we expect reward around 17.0 (plus small base), definitely > 10.0.
        
        print(f"Reward: {reward}")
        assert reward > 15.0, f"Reward {reward} should be > 15.0 (Global 15 + AvgPerRobot 2)"
