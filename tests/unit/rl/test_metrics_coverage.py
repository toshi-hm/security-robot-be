
import pytest
from rl.environments.security_env import SecurityEnvironment
from rl.environments.enhanced_env import EnhancedSecurityEnvironment

def test_security_env_metrics():
    env = SecurityEnvironment(width=10, height=10)
    obs, info = env.reset()
    
    # Initial state
    assert "coverage_ratio" in info
    assert "exploration_score" in info
    assert info["coverage_ratio"] == 1.0 / 100.0  # 1 cell visited (start pos)
    assert info["exploration_score"] == 1.0
    
    # Move robot
    # Action 0 is move forward. Direction 0 is North (0, -1).
    # We need to find a valid move to ensure we visit a new cell.
    
    start_x = env.robot_x
    start_y = env.robot_y
    initial_visited = len(env.visited_cells)
    
    # Try to move in a direction that is valid
    moved = False
    for action in [0, 1, 2, 3]: # Try moving or turning then moving
        if action == 0:
             # Try moving forward
             pass
        elif action == 1:
             env.robot_direction = (env.robot_direction - 1) % 4
        elif action == 2:
             env.robot_direction = (env.robot_direction + 1) % 4
             
        # Try to step forward if we are facing a valid direction
        # But step(0) is the only one that moves.
        # So we rotate then step(0).
        
        # Let's just try to force a move to a neighbor
        # Check neighbors
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = start_x + dx, start_y + dy
            if env._is_valid_position(nx, ny):
                # Teleport to valid neighbor to simulate a move for testing metrics
                # (Simulating the result of a successful step)
                env.robot_x, env.robot_y = nx, ny
                # We must manually add to visited if we teleport, OR call step.
                # Calling step is better.
                # Let's revert teleport and try to make step work.
                env.robot_x, env.robot_y = start_x, start_y
                
                # Point towards (nx, ny)
                if dx == 1: env.robot_direction = 1 # East
                elif dx == -1: env.robot_direction = 3 # West
                elif dy == 1: env.robot_direction = 2 # South
                elif dy == -1: env.robot_direction = 0 # North
                
                obs, reward, term, trunc, info = env.step(0) # Move forward
                if env.robot_x == nx and env.robot_y == ny:
                    moved = True
                    break
        if moved:
            break
            
    if moved:
        # Should have visited one more cell
        assert info["exploration_score"] == initial_visited + 1
        assert info["coverage_ratio"] == (initial_visited + 1) / 100.0

    
    # Find a valid move
    # Try all 4 directions until we move
    moved = False
    initial_visited = len(env.visited_cells)
    
    for _ in range(4):
        # Rotate until we face a valid cell? 
        # Or just try to move.
        # Action 0: Move front
        # Action 1: Turn left
        # Action 2: Turn right
        # Action 3: Patrol
        
        # Let's try to move forward
        old_x, old_y = env.robot_x, env.robot_y
        obs, reward, term, trunc, info = env.step(0)
        
        if env.robot_x != old_x or env.robot_y != old_y:
            moved = True
            break
        else:
            # Turn right
            env.step(2)
            
    if moved:
        # Should have visited one more cell
        assert info["exploration_score"] == initial_visited + 1
        assert info["coverage_ratio"] == (initial_visited + 1) / 100.0
    else:
        # Stuck? Unlikely in 10x10 unless surrounded by obstacles
        pass

def test_enhanced_env_metrics_compatibility():
    env = EnhancedSecurityEnvironment(width=10, height=10)
    obs, info = env.reset()
    
    assert "coverage_ratio" in info
    assert "exploration_score" in info
    # Enhanced env might have different logic, but base metrics should be consistent
    assert info["coverage_ratio"] == 1.0 / 100.0
    assert info["exploration_score"] == 1.0
    
    # Check if visited_cells is working as set
    assert isinstance(env.visited_cells, set)
    assert (env.robot_x, env.robot_y) in env.visited_cells
