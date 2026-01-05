"""
Single-agent baseline experiment script.
Runs Spiral and Zigzag (HorizontalScan) agents on the same environment as PPO training.
"""
import csv
import logging
import os
import numpy as np
from tqdm import tqdm
from datetime import datetime

from rl.environments.security_env import SecurityEnvironment
from rl.agents.template_agents import HorizontalScanAgent, SpiralAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Match PPO experiment settings
TOTAL_TIMESTEPS = 200_000
MAX_EPISODE_STEPS = 4000
LOG_INTERVAL = 250


def get_agent_class(pattern):
    if pattern == "zigzag":
        return HorizontalScanAgent
    elif pattern == "spiral":
        return SpiralAgent
    else:
        raise ValueError(f"Unknown pattern: {pattern}")


def run_single_agent_baseline(pattern, output_file):
    """Run single-agent baseline simulation."""
    logger.info(f"Starting baseline simulation: {pattern}")
    
    env = SecurityEnvironment(
        width=20,
        height=20,
        num_robots=1,
    )
    
    AgentClass = get_agent_class(pattern)
    agent = AgentClass(env.width, env.height)
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['timestep', 'episode', 'reward', 'coverage_ratio', 'threat_level_avg', 'visited_cells'])
        
        obs, info = env.reset(seed=42)
        agent.reset()
        
        # Filter obstacles from path
        if hasattr(agent, 'target_path') and agent.target_path:
            valid_path = []
            for x, y in agent.target_path:
                if 0 <= x < env.width and 0 <= y < env.height:
                    if not env.obstacles[y][x]:
                        valid_path.append((x, y))
            agent.target_path = valid_path if valid_path else [(0, 0)]
        
        episode_steps = 0
        episode_count = 1
        total_steps = 0
        episode_reward = 0.0
        
        pbar = tqdm(total=TOTAL_TIMESTEPS, desc=f"{pattern}")
        
        while total_steps < TOTAL_TIMESTEPS:
            # Get robot state
            rx, ry = env.robot_positions[0]
            rd = env.robot_directions[0]
            
            # Get obstacles
            walls = set()
            for y in range(env.height):
                for x in range(env.width):
                    if env.obstacles[y][x]:
                        walls.add((x, y))
            
            action = agent.get_action(rx, ry, rd, walls)
            obs, reward, terminated, truncated, info = env.step(np.array([action]))
            
            total_steps += 1
            episode_steps += 1
            episode_reward += reward
            pbar.update(1)
            
            # Log at interval
            if total_steps % LOG_INTERVAL == 0:
                threat = info.get('average_threat_level', 0.0)
                cov = info.get('coverage_ratio', 0.0)
                visited = info.get('visited_cells', 0)
                
                writer.writerow([
                    total_steps,
                    episode_count,
                    episode_reward,
                    cov,
                    threat,
                    visited,
                ])
                f.flush()
            
            # Episode handling
            if episode_steps >= MAX_EPISODE_STEPS:
                truncated = True
            
            if terminated or truncated:
                obs, info = env.reset()
                agent.reset()
                
                # Filter obstacles
                if hasattr(agent, 'target_path') and agent.target_path:
                    valid_path = []
                    for x, y in agent.target_path:
                        if 0 <= x < env.width and 0 <= y < env.height:
                            if not env.obstacles[y][x]:
                                valid_path.append((x, y))
                    agent.target_path = valid_path if valid_path else [(0, 0)]
                
                episode_steps = 0
                episode_count += 1
                episode_reward = 0.0
        
        pbar.close()
    
    logger.info(f"Completed: {output_file}")
    return episode_count


def main():
    patterns = ["zigzag", "spiral"]
    results = {}
    
    for pattern in patterns:
        output_csv = f"baseline_{pattern}_1_metrics.csv"
        episodes = run_single_agent_baseline(pattern, output_csv)
        results[pattern] = {"file": output_csv, "episodes": episodes}
        print(f"Done: {pattern} - {episodes} episodes")
    
    print("\n=== Summary ===")
    for pattern, data in results.items():
        print(f"{pattern}: {data['episodes']} episodes -> {data['file']}")


if __name__ == "__main__":
    main()
