
import os
import sys
import json
import time
import numpy as np
import pandas as pd

# Add app to path
sys.path.append(os.getcwd())
from rl.environments.security_env import SecurityEnvironment
from rl.agents.template_agents import HorizontalScanAgent, SpiralAgent, VerticalScanAgent

def run_baseline_experiment(agent_class, agent_name, num_episodes=50):
    print(f"Starting Baseline Experiment: {agent_name} ({num_episodes} episodes)...")
    
    # Thesis Configuration (Same as PPO)
    env_config = {
        "width": 20,
        "height": 20,
        "num_robots": 1,
        "revisit_window": 100,
        "revisit_penalty": 0.05,
        "exploration_bonus": 1.0,
        "max_episode_steps": 4000,
        "reward_normalization_mode": "mean"
    }
    
    env = SecurityEnvironment(**env_config)
    
    # Output files
    traj_file = open(f"trajectory_{agent_name}.jsonl", "w")
    monitor_data = [] # List of dicts: r, l, t, coverage, threat
    
    t_start = time.time()
    
    for ep in range(1, num_episodes + 1):
        obs, info = env.reset()
        
        # Initialize AGENT
        # Note: Template agents need width/height
        agent = agent_class(env_config["width"], env_config["height"])
        
        # Get obstacles for agent knowledge (it uses BFS)
        # Convert list of lists to set of tuples for the agent
        obstacles_set = set()
        for y in range(env.height):
            for x in range(env.width):
                if env.obstacles[y][x]:
                    obstacles_set.add((x, y))
        
        terminated = False
        truncated = False
        step_count = 0
        total_reward = 0.0
        
        # Episode Loop
        while not (terminated or truncated):
            # Get Action
            # Agent needs current state
            rx, ry = env.robot_x, env.robot_y
            r_dir = env.robot_directions[0]
            
            action = agent.get_action(rx, ry, r_dir, obstacles_set)
            
            # Step
            obs, reward, terminated, truncated, info = env.step(np.array([action]))
            
            total_reward += reward
            
            # Record Trajectory (Same schema as PPO recorder)
            state = {
                "step": (ep-1)*4000 + step_count, # Continuous step mimic
                "episode": ep,
                "robot_x": rx,
                "robot_y": ry,
                "robot_positions": env.robot_positions,
                "robot_directions": env.robot_directions,
                "battery_levels": env.battery_levels,
                "is_charging_list": env.is_charging_list,
                "threat_levels": env.threat_levels.tolist() if isinstance(env.threat_levels, np.ndarray) else env.threat_levels,
                "obstacles": env.obstacles, # Grid
                "coverage_ratio": info.get("coverage_ratio", 0.0),
                "charging_stations": env.charging_stations,
                "action": int(action),
                "reward": float(reward)
            }
            traj_file.write(json.dumps(state) + "\n")
            
            step_count += 1
            if step_count >= env_config["max_episode_steps"]:
                truncated = True
        
        # End of Episode
        # Record Monitor Data
        # Format consistent with SB3 Monitor CSV
        # r, l, t, coverage_ratio, average_threat_level
        # t is wall time? SB3 uses wall time. We can use time.time() - t_start
        t_now = time.time()
        mon_row = {
            "r": total_reward,
            "l": step_count,
            "t": t_now - t_start,
            "coverage_ratio": info.get("coverage_ratio", 0.0),
            "average_threat_level": info.get("average_threat_level", 0.0)
        }
        monitor_data.append(mon_row)
        
        if ep % 5 == 0:
            print(f"  Episode {ep}/{num_episodes}: Reward={total_reward:.1f}, Coverage={mon_row['coverage_ratio']:.3f}")
            
    traj_file.close()
    
    # Save Monitor CSV
    csv_filename = f"monitor_{agent_name}.monitor.csv"
    with open(csv_filename, "w") as f:
        f.write(f'#{{"t_start": {t_start}, "env_id": "SecurityEnv"}}\n')
        f.write("r,l,t,coverage_ratio,average_threat_level\n")
        for row in monitor_data:
            f.write(f"{row['r']},{row['l']},{row['t']},{row['coverage_ratio']},{row['average_threat_level']}\n")
            
    print(f"Saved {csv_filename} and trajectory_{agent_name}.jsonl")
    
    # Return Stats
    df = pd.DataFrame(monitor_data)
    return {
        "name": agent_name,
        "reward_mean": df["r"].mean(),
        "reward_std": df["r"].std(),
        "cov_mean": df["coverage_ratio"].mean(),
        "cov_std": df["coverage_ratio"].std(),
        "threat_mean": df["average_threat_level"].mean(),
        "threat_std": df["average_threat_level"].std()
    }

if __name__ == "__main__":
    results = []
    
    # 1. Zigzag (HorizontalScanAgent)
    stats_zigzag = run_baseline_experiment(HorizontalScanAgent, "zigzag", 50)
    results.append(stats_zigzag)
    
    # 2. Spiral (SpiralAgent)
    stats_spiral = run_baseline_experiment(SpiralAgent, "spiral", 50)
    results.append(stats_spiral)
    
    print("\n=== Baseline Results (50 Episodes) ===")
    for res in results:
        print(f"--- {res['name']} ---")
        print(f"Coverage: {res['cov_mean']:.3f} +/- {res['cov_std']:.3f}")
        print(f"Threat:   {res['threat_mean']:.3f} +/- {res['threat_std']:.3f}")
        print(f"Reward:   {res['reward_mean']:,.1f} +/- {res['reward_std']:,.1f}")
