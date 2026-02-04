
import json
import time
import numpy as np
import pandas as pd
import os
import sys

# Path setup
sys.path.append(os.getcwd())
try:
    from rl.environments.security_env import SecurityEnvironment, calculate_dynamic_max_steps
    from rl.agents.template_agents import HorizontalScanAgent, SpiralAgent
except ImportError:
    # Fallback if run from scripts dir
    sys.path.append(os.path.join(os.getcwd(), ".."))
    from rl.environments.security_env import SecurityEnvironment, calculate_dynamic_max_steps
    from rl.agents.template_agents import HorizontalScanAgent, SpiralAgent

class FixedStartSecurityEnvironment(SecurityEnvironment):
    """
    Environment with forced start positions for reproducibility.
    TL, BR, TR, BL (4 corners).
    """
    def _place_charging_station(self) -> None:
        self.charging_stations = []
        
        # User requested: TL, BR, TR, TL (Assuming BL for 4th to avoid collision)
        # 0: TL (0,0)
        # 1: BR (W-1, H-1)
        # 2: TR (W-1, 0)
        # 3: BL (0, H-1)
        
        candidates = [
            (0, 0),
            (self.width - 1, self.height - 1),
            (self.width - 1, 0),
            (0, self.height - 1)
        ]
        
        for i in range(min(self.num_robots, len(candidates))):
            x, y = candidates[i]
            # Ensure no static obstacle at start
            self.obstacles[y][x] = False
            # Ensure front is clear for initial move (Robot faces North=0 initially?)
            if y > 0: self.obstacles[y-1][x] = False
                
            self.charging_stations.append((x, y))
            
        # If more robots than 4, logic falls back (not expected for N=4)
        while len(self.charging_stations) < self.num_robots:
            # Fallback random
            import random
            x = random.randint(0, self.width-1)
            y = random.randint(0, self.height-1)
            if (x,y) not in self.charging_stations:
                self.obstacles[y][x] = False
                self.charging_stations.append((x,y))

def run_multi_agent_experiment(agent_class, agent_name, num_episodes=5):
    print(f"\nStarting Multi-Agent Baseline Experiment: {agent_name} ({num_episodes} episodes)...")
    
    # Configuration
    WIDTH = 20
    HEIGHT = 20
    NUM_ROBOTS = 4
    MAX_STEPS = 4000 # Explicitly requested
    
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
    
    env = FixedStartSecurityEnvironment(**env_config)
    
    # Output file setup
    traj_filename = f"trajectory_multi_{agent_name}.jsonl"
    traj_file = open(traj_filename, "w")
    monitor_data = [] 
    
    t_start = time.time()
    
    for ep in range(1, num_episodes + 1):
        obs, info = env.reset()
        
        # Initialize Agents
        # Initialize Agents with specific departure directions (User Request)
        # Robot 0 (TL) -> Up Focus (start_from_bottom=False) / Spiral TL
        # Robot 1 (BR) -> Down Focus (start_from_bottom=True) / Spiral BR
        # Robot 2 (TR) -> Up Focus (start_from_bottom=False) / Spiral TR
        # Robot 3 (BL) -> Down Focus (start_from_bottom=True) / Spiral BL
        
        corners = ["TL", "BR", "TR", "BL"]
        agents = []
        for i in range(NUM_ROBOTS):
            start_bottom = (i == 1 or i == 3)
            start_c = corners[i % 4]
            
            if agent_class == HorizontalScanAgent:
                agents.append(agent_class(WIDTH, HEIGHT, start_from_bottom=start_bottom))
            elif agent_class == SpiralAgent:
                agents.append(agent_class(WIDTH, HEIGHT, start_corner=start_c))
            else:
                agents.append(agent_class(WIDTH, HEIGHT))
        
        # Static Obstacles Set
        static_obstacles = set()
        for y in range(HEIGHT):
            for x in range(WIDTH):
                if env.obstacles[y][x]:
                    static_obstacles.add((x, y))
        
        terminated = False
        truncated = False
        step_count = 0
        total_reward = 0.0
        
        # Metrics Tracking
        coverage_100_step = None
        
        while not (terminated or truncated):
            actions = []
            
            # Strategy: Strict Sequential Reservation (Safe Priority)
            # 1. Higher Priority robots move first and 'reserve' their cell.
            # 2. Lower Priority robots see 'reserved' cells as obstacles.
            # 3. SAFETY: All robots treat CURRENT POSITIONS of lower-id robots as obstacles to prevent crashing into sitting ducks.
            #    (Optimization: This allows 'following' because we don't treat Higher-ID OLD positions as obstacles, only their TARGETS)
            
            # Build Plan Sequentially
            next_positions = [None] * NUM_ROBOTS
            
            # Loop through robots in order of Priority (0 -> N-1)
            for i in range(NUM_ROBOTS):
                agent = agents[i]
                rx, ry = env.robot_positions[i]
                r_dir = env.robot_directions[i]
                
                # Build Obstacles for Robot i
                current_obstacles = static_obstacles.copy()
                
                # A. Add Reserved Next Positions of Higher Priority Robots (0 to i-1)
                # These cells will be occupied at t+1
                for prev_i in range(i):
                    if next_positions[prev_i]:
                        current_obstacles.add(next_positions[prev_i])
                        
                # B. Add Current Positions of Lower Priority Robots (i+1 to N)
                # We assume they haven't moved yet, so we can't move into them unless we know they clear out.
                # Safe Baseline Policy: Treat them as static obstacles.
                for next_i in range(i + 1, NUM_ROBOTS):
                    current_obstacles.add(env.robot_positions[next_i])

                # Get Action
                try:
                    action = agent.get_action(rx, ry, r_dir, current_obstacles)
                except Exception:
                    action = 3 # Stay

                # Calculate Intended Next Position to Reserve it
                dx, dy = [(0, -1), (1, 0), (0, 1), (-1, 0)][(r_dir if action == 0 else -1) % 4] # dummy if not moving
                if action == 0:
                    # Move Forward
                    # Direction check: SecurityEnv updates dict on turn, but here we read Current Dict
                    # So if action is Move, we use current Dir.
                    tx, ty = rx + dx, ry + dy
                else:
                    # Turn or Stay -> Occupy Current Cell
                    tx, ty = rx, ry
                    
                # Reserve
                next_positions[i] = (tx, ty)
                actions.append(action)
            
            # Step Environment
            obs, reward, terminated, truncated, info = env.step(np.array(actions))
            
            total_reward += reward
            
            # Coverage 100% check
            cov = info.get("coverage_ratio", 0.0)
            if cov >= 1.0 and coverage_100_step is None:
                coverage_100_step = step_count
            
            # Log Trajectory (Extended for Multi-Agent)
            state = {
                "step": (ep-1)*MAX_STEPS + step_count,
                "episode": ep,
                "robot_positions": [list(p) for p in env.robot_positions],
                "robot_directions": env.robot_directions,
                "battery_levels": env.battery_levels,
                "is_charging_list": env.is_charging_list,
                # Flatten grids for JSON size
                "threat_levels": env.threat_levels if isinstance(env.threat_levels, list) else env.threat_levels.tolist(),
                "obstacles": env.obstacles,
                "coverage_ratio": cov,
                "charging_stations": env.charging_stations,
                "actions": [int(a) for a in actions],
                "reward": float(reward),
                
                # Extra PPO-like metrics placeholders
                "approx_kl": 0.0,
                "clip_fraction": 0.0,
                "entropy_loss": 0.0,
                "policy_gradient_loss": 0.0,
                "value_loss": 0.0,
                "explained_variance": 0.0
            }
            traj_file.write(json.dumps(state) + "\n")
            
            step_count += 1
            if step_count >= MAX_STEPS:
                truncated = True
        
        # Episode End Metrics
        t_now = time.time()
        mon_row = {
            "r": total_reward, 
            "l": step_count,
            "t": t_now - t_start,
            "coverage_ratio": info.get("coverage_ratio", 0.0),
            "average_threat_level": info.get("average_threat_level", 0.0),
            "coverage_100_step": coverage_100_step if coverage_100_step else MAX_STEPS,
            # PPO metrics
            "approx_kl": 0.0,
            "clip_fraction": 0.0,
            "entropy_loss": 0.0,
            "policy_gradient_loss": 0.0,
            "value_loss": 0.0,
            "explained_variance": 0.0
        }
        monitor_data.append(mon_row)
        
        print(f"  Episode {ep}/{num_episodes}: Reward={total_reward:.1f}, Cov={mon_row['coverage_ratio']:.3f}, Threat={mon_row['average_threat_level']:.3f}")

    traj_file.close()
    
    # Save CSV
    csv_filename = f"monitor_multi_{agent_name}.csv"
    df = pd.DataFrame(monitor_data)
    df.to_csv(csv_filename, index=False)
    print(f"Saved {csv_filename} and {traj_filename}")
    
    return df

if __name__ == "__main__":
    # Run for Zigzag and Spiral
    # User requested 50 episodes x 4000 steps
    EPISODES = 50
    
    results = {}
    
    # 1. Zigzag
    print("=== Running ZIGZAG (N=4) ===")
    df_zigzag = run_multi_agent_experiment(HorizontalScanAgent, "zigzag", EPISODES)
    results["zigzag"] = df_zigzag
    
    # 2. Spiral
    print("=== Running SPIRAL (N=4) ===")
    df_spiral = run_multi_agent_experiment(SpiralAgent, "spiral", EPISODES)
    results["spiral"] = df_spiral
    
    print("\n=== Summary Stats (N=4) ===")
    for name, df in results.items():
        print(f"--- {name} ---")
        print(f"Reward: {df['r'].mean():.1f} (+/- {df['r'].std():.1f})")
        print(f"Coverage: {df['coverage_ratio'].mean():.3f}")
        print(f"Time to 100%: {df['coverage_100_step'].mean():.1f}")
