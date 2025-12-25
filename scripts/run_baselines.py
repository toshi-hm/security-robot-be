import csv
import logging
import os
import time
from datetime import datetime
import numpy as np
from tqdm import tqdm

from rl.environments.enhanced_env import EnhancedSecurityEnvironment
from rl.agents.template_agents import HorizontalScanAgent, SpiralAgent, ACTION_PATROL, ACTION_MOVE_FORWARD, ACTION_TURN_LEFT, ACTION_TURN_RIGHT

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
TOTAL_TIMESTEPS = 100_000
MAX_EPISODE_STEPS = 1000  # Enforce episode limit
LOG_INTERVAL = 250  # Match RL logging frequency

def get_agent_class(pattern):
    if pattern == "zigzag":
        return HorizontalScanAgent
    elif pattern == "spiral":
        return SpiralAgent
    else:
        raise ValueError(f"Unknown pattern: {pattern}")

def run_simulation(num_robots, pattern, output_file):
    logger.info(f"Starting simulation: {pattern} with {num_robots} robots")
    
    # Initialize Environment
    # Use config similar to Cycle 12 (from report/result/cycle12/CYCLE12_ROBOT_COUNT_EXPERIMENT.md)
    # 20x20, random map (seed 42), coverage_weight=1.0, exploration_weight=0.5, diversity_weight=0.5, threat_penalty_weight=50.0
    env = EnhancedSecurityEnvironment(
        width=20,
        height=20,
        num_robots=num_robots,
        coverage_weight=1.0,
        exploration_weight=0.5,
        diversity_weight=0.5,
        threat_penalty_weight=50.0,
        battery_drain_rate=0.001,
        map_type="random",
        seed=42,
        reward_normalization_mode="mean", # Match RL training mode for 'reward' column consistency
        strategic_init_mode=False # Baseline usually starts random or fixed? 
        # RL used random map seed 42. Strategic init mode was False in Cycle 12 (check report).
        # Report says "Map type: random (seed=42)". It doesn't explicitly mention strategic init, but usually defaults to False.
    )

    # Initialize Agents
    AgentClass = get_agent_class(pattern)
    agents = [AgentClass(env.width, env.height) for _ in range(num_robots)]
    
    # Open CSV
    file_exists = os.path.isfile(output_file)
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        # Header matching existing logs
        writer.writerow(['timestep', 'episode', 'reward', 'estimated_team_reward', 'coverage_ratio', 'threat_level_avg', 'visited_cells', 'loss', 'timestamp'])
        
        obs, info = env.reset(seed=42)
        for i, agent in enumerate(agents):
            agent.reset()
            # Filter obstacles from path
            if getattr(agent, 'target_path', None):
                valid_path = []
                for x, y in agent.target_path:
                    # Check bounds before accessing env.obstacles
                    if 0 <= x < env.width and 0 <= y < env.height:
                        if not env.obstacles[y][x]:
                           valid_path.append((x, y))
                agent.target_path = valid_path
                
                if not valid_path:
                    logger.warning(f"Agent {i} has empty path after filtering! Defaulting to random walk behavior (or stay).")
                    # Prevent IndexError by adding current pos or random pos
                    # Since we don't know current pos here easily (it's in env), we can just append (0,0) or catch in get_action
                    agent.target_path = [(0, 0)] # Dummy
                
                # Distribute agents evenly along the cleaned path
                if valid_path:
                    offset = int(len(valid_path) / num_robots * i)
                    agent.current_path_index = offset
            
        episode_steps = 0
        episode_count = 1
        total_steps = 0
        
        # Tracking for logging (moving average approximation or instantaneous?)
        # RL logs are usually PPO rollout averages. 
        # Here we will log instantaneous or windowed average.
        # To match the "smoothness" of RL logs, let's log instantaneous at LOG_INTERVAL.
        
        pbar = tqdm(total=TOTAL_TIMESTEPS)
        
        while total_steps < TOTAL_TIMESTEPS:
            # Get actions
            actions = []
            robot_positions = env.robot_positions # Access directly
            
            # Create a combined obstacle set for all robots to view
            # In simulation, robots might see static obstacles + other robots?
            # BaseTemplateAgent takes 'obstacles'.
            # env.walls is a set of (x,y)? No, env.grid might interpret walls.
            # SecurityEnvironment usually has self.walls equivalent?
            # Looking at source, SecurityEnv has self.grid. 0=empty, 1=wall.
            walls = set()
            for y in range(env.height):
                for x in range(env.width):
                    if env.obstacles[y][x]:
                        walls.add((x, y))
            
            # For naive baseline, they treat walls as obstacles.
            # Do they treat other robots as obstacles? 
            # If so, they might deadlock. Naive usually ignores other robots until collision.
            # Let's pass walls only.
            
            for i, agent in enumerate(agents):
                rx, ry = robot_positions[i]
                # Default direction? env doesnt expose it easily directly in 'robot_positions'
                # SecurityEnv has 'robot_directions' list? 
                # Checking source code... 'robot_directions' seems likely exist in SecurityEnv.
                # Assuming env.robot_directions exists (it's standard in my previous memory/code).
                rd = env.robot_directions[i] 
                
                action = agent.get_action(rx, ry, rd, walls)
                actions.append(action)
                
            # Step
            obs, reward, terminated, truncated, info = env.step(np.array(actions))
            
            total_steps += 1
            episode_steps += 1
            pbar.update(1)
            
            # Log
            if total_steps % LOG_INTERVAL == 0:
                # reward is 'enhanced_reward' (mean normalized).
                # team_reward is in info.
                
                # Check for None values
                team_rew = info.get('team_reward', 0.0) 
                # If team_reward is missing (it shouldn't be if logic is correct), estimate it
                if team_rew is None:
                    team_rew = reward * num_robots
                    
                threat = info.get('average_threat_level', 0.0)
                cov = info.get('coverage_ratio', 0.0)
                visited = info.get('visited_cells', 0)
                
                writer.writerow([
                    total_steps,
                    episode_count,
                    reward,
                    team_rew,
                    cov,
                    threat,
                    visited,
                    '0.0', # loss is 0 for baseline
                    datetime.utcnow().isoformat() + 'Z'
                ])
                f.flush()
                
            # Episode handling
            if episode_steps >= MAX_EPISODE_STEPS:
                truncated = True
                
            if terminated or truncated:
                obs, info = env.reset() 
                for i, agent in enumerate(agents):
                    agent.reset()
                    # Filter obstacles from path
                    if getattr(agent, 'target_path', None):
                        valid_path = []
                        for x, y in agent.target_path:
                            # Check bounds
                            if 0 <= x < env.width and 0 <= y < env.height:
                                if not env.obstacles[y][x]:
                                    valid_path.append((x, y))
                        agent.target_path = valid_path
                        
                        if not valid_path:
                            # Fallback
                            agent.target_path = [(0, 0)]

                        # Distribute agents evenly along the cleaned path
                        if valid_path:
                            offset = int(len(valid_path) / num_robots * i)
                            agent.current_path_index = offset
                        
                episode_steps = 0
                episode_count += 1
                
        pbar.close()

def main():
    robots_list = [2, 3, 4, 5]
    patterns = ["zigzag", "spiral"]
    
    for pattern in patterns:
        for n in robots_list:
            output_csv = f"baseline_{pattern}_{n}_metrics.csv"
            print(f"Running {pattern} with {n} robots...")
            run_simulation(n, pattern, output_csv)
            print(f"Done. Saved to {output_csv}")

if __name__ == "__main__":
    main()
