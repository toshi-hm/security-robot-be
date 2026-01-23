
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

SESSION_MAP = {
    116: {"robots": 1, "color": "purple"},
    117: {"robots": 2, "color": "blue"},
    118: {"robots": 3, "color": "green"},
    119: {"robots": 4, "color": "red"}
}

OUTPUT_FILE = "multi_agent_rewards_117_118_119.json"

def export_multi_agent_rewards():
    print(f"Exporting Reward Data for Sessions {list(SESSION_MAP.keys())}...")
    
    all_data = {}
    
    with SessionLocal() as session:
        for sess_id, meta in SESSION_MAP.items():
            print(f"Querying Session {sess_id} ({meta['robots']} robots)...")
            
            # Query trainingmetric for episode rewards
            # Assuming 'reward' column stores the episode reward
            query = text("""
                SELECT episode, reward
                FROM trainingmetric 
                WHERE job_id = :sess_id 
                ORDER BY episode ASC
            """)
            
            result = session.execute(query, {"sess_id": sess_id})
            rows = result.fetchall()
            
            if not rows:
                print(f"Warning: No data for Session {sess_id}")
                continue
                
            # Convert to list of dicts
            rewards = []
            episodes = []
            for row in rows:
                if row.reward is None:
                     continue
                episodes.append(row.episode)
                rewards.append(float(row.reward))
            
            all_data[sess_id] = {
                "robots": meta["robots"],
                "color": meta["color"],
                "episodes": episodes,
                "rewards": rewards
            }
            print(f"  Got {len(episodes)} episodes.")

    with open(OUTPUT_FILE, "w") as f:
        json.dump(all_data, f, indent=2)
    
    print(f"Export complete. Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    export_multi_agent_rewards()
