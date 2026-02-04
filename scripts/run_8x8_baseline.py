
import json
import time
import numpy as np
import pandas as pd
import os
import sys

# Path setup
sys.path.append(os.getcwd())
try:
    from rl.environments.security_env import SecurityEnvironment
    from rl.agents.template_agents import HorizontalScanAgent, SpiralAgent
except ImportError:
    sys.path.append(os.path.join(os.getcwd(), ".."))
    from rl.environments.security_env import SecurityEnvironment
    from rl.agents.template_agents import HorizontalScanAgent, SpiralAgent

def run_baseline_experiment(agent_class, agent_name, num_episodes=50):
    print(f"\nStarting 8x8 Single Agent Baseline: {agent_name} ({num_episodes} episodes)...")
    
    # 8x8 Configuration
    WIDTH = 8
    HEIGHT = 8
    NUM_ROBOTS = 1
    MAX_STEPS = 4000
    
    env_config = {
        "width": WIDTH,
        "height": HEIGHT,
        "num_robots": NUM_ROBOTS,
        "revisit_window": 100,
        "revisit_penalty": 0.05,
        "exploration_bonus": 1.0,
        "max_episode_steps": MAX_STEPS,
        "reward_normalization_mode": "mean",
        "map_type": "random"
    }
    
    env = SecurityEnvironment(**env_config)
    
    traj_filename = f"trajectory_8x8_{agent_name}.jsonl"
    traj_file = open(traj_filename, "w")
    monitor_data = [] 
    
    t_start = time.time()
    
    for ep in range(1, num_episodes + 1):
        obs, info = env.reset()
        
        # Initialize Agent
        if agent_class == HorizontalScanAgent:
            # Default Zigzag
            agent = agent_class(WIDTH, HEIGHT)
        elif agent_class == SpiralAgent:
            # Spiral from TL by default
            agent = agent_class(WIDTH, HEIGHT, start_corner="TL")
        else:
            agent = agent_class(WIDTH, HEIGHT)
        
        # For single agent, we might need to set the agent's internal position if it tracks it?
        # The template agents usually calculate based on current pos or internal state.
        # Let's assume they are stateless or updated.
        # Looking at previous usage, they take (x,y) in get_action.
        
        terminated = False
        truncated = False
        step_count = 0
        total_reward = 0.0
        
        coverage_100_step = None
        
        while not (terminated or truncated):
            rx, ry = env.robot_positions[0]
            r_dir = env.robot_directions[0]
            
            # Static Obstacles
            current_obstacles = set()
            for y in range(HEIGHT):
                for x in range(WIDTH):
                    if env.obstacles[y][x]:
                        current_obstacles.add((x, y))
            
            try:
                action = agent.get_action(rx, ry, r_dir, current_obstacles)
            except Exception:
                action = 3 # Stay
            
            # Step Environment
            # Single agent action needs to be array? Env expects array if num_robots > 1?
            # SecurityEnvironment handles scalar or array for N=1?
            # Let's look at env code or assume array is safe.
            actions = np.array([action])
            
            obs, reward, terminated, truncated, info = env.step(actions)
            
            # If reward is array (N=1), take scalar
            if isinstance(reward, (list, np.ndarray)):
                reward_scalar = float(reward[0] if len(reward) > 0 else reward)
            else:
                reward_scalar = float(reward)
            
            total_reward += reward_scalar
            
            # Check coverage 100%
            cov = info.get("coverage_ratio", 0.0)
            if cov >= 1.0 and coverage_100_step is None:
                coverage_100_step = step_count
            
            # Log Trajectory
            state = {
                "step": (ep-1)*MAX_STEPS + step_count,
                "episode": ep,
                "robot_positions": [list(p) for p in env.robot_positions],
                "robot_directions": env.robot_directions,
                "battery_levels": env.battery_levels,
                "is_charging_list": env.is_charging_list,
                "threat_levels": env.threat_levels if isinstance(env.threat_levels, list) else env.threat_levels.tolist(),
                "obstacles": env.obstacles,
                "coverage_ratio": cov,
                "charging_stations": env.charging_stations,
                "average_threat_level": info.get("average_threat_level", 0.0), # Add average threat
                "actions": [int(action)],
                "reward": reward_scalar
            }
            traj_file.write(json.dumps(state) + "\n")
            
            step_count += 1
            if step_count >= MAX_STEPS:
                truncated = True
        
        t_now = time.time()
        mon_row = {
            "r": total_reward, 
            "l": step_count,
            "t": t_now - t_start,
            "coverage_ratio": info.get("coverage_ratio", 0.0),
            "average_threat_level": info.get("average_threat_level", 0.0),
            "coverage_100_step": coverage_100_step if coverage_100_step else MAX_STEPS
        }
        monitor_data.append(mon_row)
        
        if ep % 10 == 0:
            print(f"  Episode {ep}/{num_episodes}: Reward={total_reward:.1f}, Cov={mon_row['coverage_ratio']:.3f}, Threat={mon_row['average_threat_level']:.3f}")

    traj_file.close()
    
    csv_filename = f"monitor_8x8_{agent_name}.csv"
    df = pd.DataFrame(monitor_data)
    df.to_csv(csv_filename, index=False)
    print(f"Saved {csv_filename} and {traj_filename}")
    
    return df

if __name__ == "__main__":
    EPISODES = 50
    
    results = {}
    
    print("=== Running ZIGZAG (8x8) ===")
    results["zigzag"] = run_baseline_experiment(HorizontalScanAgent, "zigzag", EPISODES)
    
    print("=== Running SPIRAL (8x8) ===")
    results["spiral"] = run_baseline_experiment(SpiralAgent, "spiral", EPISODES)
    
    print("\n=== Summary Stats (8x8) ===")
    for name, df in results.items():
        print(f"--- {name} ---")
        print(f"Reward: {df['r'].mean():.1f}")
        print(f"Avg Threat: {df['average_threat_level'].mean():.3f}")
        print(f"Coverage: {df['coverage_ratio'].mean():.3f}")
