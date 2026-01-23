
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

OUTPUT_FILE = "multi_agent_coverage_data.json"

def export_coverage_data():
    print(f"Exporting Coverage Data for Sessions {list(SESSION_MAP.keys())}...")
    
    all_data = {}
    
    with SessionLocal() as session:
        for sess_id, meta in SESSION_MAP.items():
            print(f"Querying Session {sess_id} ({meta['robots']} robots)...")
            
            # Query relevant columns
            query = text("""
                SELECT episode, step, coverage_ratio
                FROM environmentstate 
                WHERE session_id = :sess_id 
                ORDER BY step ASC
            """)
            
            result = session.execute(query, {"sess_id": sess_id})
            rows = result.fetchall()
            
            if not rows:
                print(f"Warning: No data for Session {sess_id}")
                continue
            
            episodes = {}
            
            for row in rows:
                ep = row.episode
                step = row.step
                cov = float(row.coverage_ratio if row.coverage_ratio is not None else 0.0)
                
                if ep not in episodes:
                    episodes[ep] = {
                        "start_step": step,
                        "end_step": step,
                        "max_coverage": 0.0,
                        "step_reached_100": None
                    }
                
                ep_data = episodes[ep]
                if step < ep_data["start_step"]: ep_data["start_step"] = step
                if step > ep_data["end_step"]: ep_data["end_step"] = step
                
                if cov > ep_data["max_coverage"]:
                    ep_data["max_coverage"] = cov
                
                # Check 100% (or roughly 1.0)
                if ep_data["step_reached_100"] is None and cov >= 1.0:
                    ep_data["step_reached_100"] = step
            
            # Aggregate per episode
            ep_list = sorted(episodes.keys())
            coverage_list = []
            steps_list = [] # Steps to 100% or None/End? 
            # For plotting "Steps to 100% Coverage", if it didn't reach, what to do?
            # User wants trend. If 1.0 not reached, maybe max steps? 
            # Given previous results, most reached 1.0 except maybe the last one.
            
            cleaned_episodes = []
            
            for ep in ep_list:
                data = episodes[ep]
                
                duration_to_100 = None
                if data["step_reached_100"] is not None:
                    duration_to_100 = data["step_reached_100"] - data["start_step"]
                
                # If didn't reach 100%, we might exclude from the "steps" plot or use full duration
                # For now, append None if not reached, handle in plotter
                
                if duration_to_100 is None and data["max_coverage"] < 1.0:
                    # Treat as None (will break line in plot or be skipped)
                     pass
                elif duration_to_100 is None: 
                    # Max coverage >= 1.0 but logic missed it? Unlikely.
                    # Or maybe started at 1.0? 0 steps.
                    duration_to_100 = data["end_step"] - data["start_step"] # Fallback
                
                cleaned_episodes.append(ep)
                coverage_list.append(data["max_coverage"])
                steps_list.append(duration_to_100)

            all_data[sess_id] = {
                "robots": meta["robots"],
                "color": meta["color"],
                "episodes": cleaned_episodes,
                "max_coverage": coverage_list,
                "steps_to_100": steps_list
            }
            print(f"  Processed {len(cleaned_episodes)} episodes.")

    with open(OUTPUT_FILE, "w") as f:
        json.dump(all_data, f, indent=2)
    
    print(f"Export complete. Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    export_coverage_data()
