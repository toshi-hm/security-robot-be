
import sys
import os
import json
from sqlalchemy import text
from dotenv import load_dotenv

sys.path.append(os.getcwd())
load_dotenv()
if os.getenv('DATABASE_URL'):
    os.environ['DATABASE_URL'] = os.getenv('DATABASE_URL').replace("@postgres:", "@localhost:")

from app.db.session import SessionLocal

# Sessions to export
SESSION_MAP = {
    117: {"robots": 2},
    118: {"robots": 3},
    119: {"robots": 4}
}

# Export ALL episodes
EPISODES = list(range(1, 51))

OUTPUT_FILE = "multi_agent_trajectories_all.json"

def export_trajectories():
    print(f"Exporting Trajectories for Sessions {list(SESSION_MAP.keys())}, Episodes 1-50...")
    
    all_data = {}
    
    with SessionLocal() as session:
        for sess_id, meta in SESSION_MAP.items():
            print(f"Querying Session {sess_id} ({meta['robots']} robots)...")
            
            sess_data = {
                "robots_count": meta["robots"],
                "episodes": {}
            }
            
            for ep in EPISODES:
                if ep % 10 == 0:
                    print(f"  Fetching Episode {ep}...")
                
                query = text("""
                    SELECT step, robots, obstacles
                    FROM environmentstate 
                    WHERE session_id = :sess_id AND episode = :ep
                    ORDER BY step ASC
                """)
                
                result = session.execute(query, {"sess_id": sess_id, "ep": ep})
                rows = result.fetchall()
                
                if not rows:
                    print(f"    Warning: No data for Ep {ep}")
                    continue
                
                trajectories = {} 
                obstacles = []
                
                # Search for obstacles in any row
                if not obstacles:
                    for row in rows:
                        if row.obstacles:
                            obs_raw = row.obstacles
                            if isinstance(obs_raw, str):
                                obs_raw = json.loads(obs_raw)
                            
                            # Normalize
                            temp_obs = []
                            # Check if it's a grid (list of lists)
                            if isinstance(obs_raw, list) and len(obs_raw) > 0 and isinstance(obs_raw[0], list):
                                for y, grid_row in enumerate(obs_raw):
                                    for x, is_blocked in enumerate(grid_row):
                                        if is_blocked:
                                            temp_obs.append([x, y])
                            else:
                                for o in obs_raw:
                                    if isinstance(o, dict):
                                        temp_obs.append([o['x'], o['y']])
                                    elif isinstance(o, list):
                                        temp_obs.append(o)
                            
                            if temp_obs:
                                obstacles = temp_obs
                                break
                
                for row in rows:
                    step_robots = row.robots
                    if not step_robots:
                        continue
                    if isinstance(step_robots, str):
                        step_robots = json.loads(step_robots)
                    
                    for i, robot in enumerate(step_robots):
                        r_id = i 
                        if r_id not in trajectories:
                            trajectories[r_id] = []
                        
                        trajectories[r_id].append([robot['x'], robot['y']])
                
                sess_data["episodes"][ep] = {
                    "trajectories": trajectories,
                    "obstacles": obstacles
                }
            
            all_data[sess_id] = sess_data

    with open(OUTPUT_FILE, "w") as f:
        json.dump(all_data, f)
    
    print(f"Export complete. Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    export_trajectories()
