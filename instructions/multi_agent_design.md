# Multi-Agent Design Document

This document outlines the design decisions and strategies for the multi-agent reinforcement learning environment in `security-robot-be`.

## Collision Resolution Strategy

The environment uses a priority-based collision resolution mechanism to handle multiple robots moving simultaneously.

### 1. Vertex Collision (Same Target)
When multiple robots attempt to move to the same grid cell:
- **Detection**: The system identifies all robots targeting the same coordinate.
- **Resolution**: All involved robots are denied movement and remain at their current positions.
- **Penalty**: A collision penalty is applied to all involved robots. The penalty scales with the number of robots involved to discourage congestion.
  - Formula: `Penalty = -COLLISION_BASE_PENALTY * num_robots * scale_factor`
  - Scale Factor: `1.0 + (num_robots - 2) * 0.3`

### 2. Swap Collision (Edge Collision)
When two robots attempt to swap positions (Robot A moves to B's position, Robot B moves to A's position):
- **Detection**: The system checks if `target_pos[i] == current_pos[j]` and `target_pos[j] == current_pos[i]`.
- **Resolution**: Both robots are denied movement and remain at their current positions.
- **Penalty**: A fixed collision penalty (`-COLLISION_BASE_PENALTY`) is applied to both robots.

### 3. Corner Collision
When a robot attempts to move into a wall or obstacle:
- **Detection**: The system checks if the target position is within bounds and not an obstacle.
- **Resolution**: The robot remains at its current position.
- **Penalty**: A collision penalty is applied.

## Reward Scaling

Rewards are scaled to ensure stable training across different numbers of robots.

- **Coverage Reward**: Shared among all robots.
  - `+1.0` for visiting a new cell (global).
  - `+0.1` for re-visiting a cell (global, with decay).
- **Exploration Reward**: Individual reward for exploring new areas.
- **Collision Penalty**: Negative reward as described above.

## Recommended Hyperparameters

For multi-agent training (PPO/A3C), the following hyperparameters are recommended based on the number of robots:

| Num Robots | Learning Rate | Batch Size | Entropy Coeff |
| :--- | :--- | :--- | :--- |
| 1 | 3e-4 | 64 | 0.01 |
| 2-4 | 2.5e-4 | 128 | 0.01 |
| 5-10 | 2e-4 | 256 | 0.02 |

*Note: As the number of robots increases, the state space complexity grows. Increasing the batch size and slightly reducing the learning rate helps stabilize training.*
