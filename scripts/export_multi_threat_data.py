
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

SESSION_MAP = {
    116: {"robots": 1, "color": "purple"},
    117: {"robots": 2, "color": "blue"},
    118: {"robots": 3, "color": "green"},
    119: {"robots": 4, "color": "red"}
}

OUTPUT_FILE = "multi_agent_threat_data.json"

def export_threat_data():
    print(f"Exporting Threat Data for Sessions {list(SESSION_MAP.keys())}...")
    
    all_data = {}
    
    with SessionLocal() as session:
        for sess_id, meta in SESSION_MAP.items():
            print(f"Querying Session {sess_id} ({meta['robots']} robots)...")
            
            # Query average_threat_level from trainingmetric
            # Correct column name: threat_level_avg
            query = text("""
                SELECT episode, threat_level_avg
                FROM trainingmetric 
                WHERE job_id = :sess_id 
                ORDER BY episode ASC
            """)
            
            result = session.execute(query, {"sess_id": sess_id})
            rows = result.fetchall()
            
            if not rows:
                print(f"Warning: No data for Session {sess_id}")
                continue
            
            episodes = []
            threats = []
            for row in rows:
                if row.threat_level_avg is None:
                    continue
                episodes.append(row.episode)
                threats.append(float(row.threat_level_avg))
            
            all_data[sess_id] = {
                "robots": meta["robots"],
                "color": meta["color"],
                "episodes": episodes,
                "threats": threats
            }
            print(f"  Got {len(episodes)} episodes.")

    with open(OUTPUT_FILE, "w") as f:
        json.dump(all_data, f, indent=2)
    
    print(f"Export complete. Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    export_threat_data()
