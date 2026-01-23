
import sys
import os
import json
from sqlalchemy import text
from dotenv import load_dotenv

# Add app to path
sys.path.append(os.getcwd())

# Load .env and override for localhost
load_dotenv()
if os.getenv('DATABASE_URL'):
    os.environ['DATABASE_URL'] = os.getenv('DATABASE_URL').replace("@postgres:", "@localhost:")

from app.db.session import SessionLocal

OUTPUT_FILE = "trajectory_session_116.jsonl"

def export_session_116():
    print(f"Exporting Session 116 into {OUTPUT_FILE}...")
    
    with SessionLocal() as session:
        # Query EnvironmentState for session_id=116
        # Order by episode, step
        query = text("""
            SELECT 
                step, episode, 
                robot_x, robot_y, 
                robots, obstacles, 
                coverage_ratio, 
                threat_grid, battery_percentage
            FROM environmentstate 
            WHERE session_id = 116 
            ORDER BY episode, step
        """)
        
        result = session.execute(query)
        rows = result.fetchall()
        
        if not rows:
            print("No data found for session_id=116")
            return

        print(f"Found {len(rows)} rows for Session 116.")
        
        episodes = set()
        
        with open(OUTPUT_FILE, "w") as f:
            for row in rows:
                # row is a tuple-like object, access by index or key?
                # SQLAlchemy rows can be accessed by column name
                
                # Reconstruct dict matching JSONL format expected by plotting script
                # JSONL format: {"step": 1, "episode": 1, "robot_x": ..., "robot_y": ..., "obstacles": ...}
                
                # Check if robots/obstacles are string (JSON) or dict
                # SQLAlchemy with JSON type might return dict automatically or string depending on driver
                # asyncpg/psycopg usually returns dict for JSON columns
                
                robots_data = row.robots
                obstacles_data = row.obstacles
                
                # Ensure JSON serializable
                state = {
                    "step": row.step,
                    "episode": row.episode,
                    "robot_x": row.robot_x,
                    "robot_y": row.robot_y,
                    "robot_positions": robots_data, 
                    "obstacles": obstacles_data,
                    "coverage_ratio": row.coverage_ratio,
                    # Add others if needed
                }
                
                f.write(json.dumps(state) + "\n")
                episodes.add(row.episode)
                
        print(f"Export complete. Episodes found: {sorted(list(episodes))}")
        print(f"Total Episodes: {len(episodes)}")
        
if __name__ == "__main__":
    export_session_116()
