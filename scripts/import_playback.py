
import asyncio
import json
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.models.training import TrainingJob
from app.models.environment import EnvironmentState
from datetime import datetime

# Connect to Postgres (using async driver)
DATABASE_URL = "postgresql+asyncpg://security_robot:change_me@localhost:5432/security_robot"
engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# File paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = [
    {"name": "Baseline Spiral (Single)", "path": os.path.join(BASE_DIR, "trajectory_spiral.jsonl"), "type": "spiral"},
    {"name": "Baseline Zigzag (Single)", "path": os.path.join(BASE_DIR, "trajectory_zigzag.jsonl"), "type": "zigzag"},
    {"name": "Baseline Spiral (Multi)", "path": os.path.join(BASE_DIR, "trajectory_multi_spiral.jsonl"), "type": "spiral_multi"},
    {"name": "Baseline Zigzag (Multi)", "path": os.path.join(BASE_DIR, "trajectory_multi_zigzag.jsonl"), "type": "zigzag_multi"}
]

async def create_job_if_not_exists(db: AsyncSession, name: str, job_type: str):
    stmt = select(TrainingJob).filter(TrainingJob.name == name)
    result = await db.execute(stmt)
    job = result.scalars().first()
    
    if job:
        print(f"Job '{name}' already exists with ID {job.id}. Deleting to re-import...")
        await db.delete(job)
        await db.commit()
    
    # Create new job
    job = TrainingJob(
        name=name,
        status="completed",
        algorithm="ppo", # Required field, using 'ppo' as placeholder for baseline
        environment_type="standard", # Required field
        created_at=datetime.utcnow(),
        total_timesteps=0,
        current_timestep=0,
        config={"algorithm": "dijkstra" if job_type == "spiral" else "dijkstra", "type": job_type}
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    print(f"Created Job '{name}' with ID {job.id}")
    return job, True

async def import_file(db: AsyncSession, file_info):
    job, is_new = await create_job_if_not_exists(db, file_info["name"], file_info["type"])
    if not is_new:
        return

    filepath = file_info["path"]
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return

    print(f"Importing {filepath} to Job ID {job.id}...")
    
    batch_size = 100
    batch = []
    
    with open(filepath, 'r') as f:
        for idx, line in enumerate(f):
            if idx > 5000:
                print(f"Reached limit of 5000 lines for {file_info['name']}. Stopping import for this file.")
                break
            try:
                data = json.loads(line)
                
                episode = data.get("episode", 1)
                step = data.get("step", 0)
                
                rx, ry = 0, 0
                orientation = 0
                battery = 100.0
                
                if "robot_positions" in data and len(data["robot_positions"]) > 0:
                    rp = data["robot_positions"][0]
                    if isinstance(rp, dict):
                        rx = rp.get("x", 0)
                        ry = rp.get("y", 0)
                        orientation = rp.get("orientation", 0)
                        battery = rp.get("battery_percentage", 100.0)
                    elif isinstance(rp, list):
                        rx = rp[0]
                        ry = rp[1]
                        
                        # Fix: Extract orientation from robot_directions if available
                        raw_directions = data.get("robot_directions", [])
                        if raw_directions and isinstance(raw_directions, list) and len(raw_directions) > 0:
                            # Handle single agent or N agents
                            # Assuming robot_positions[0] corresponds to robot_directions[0]
                            # Start index logic is simplified here for single agent focal point
                            orientation = raw_directions[0]
                else:
                    rx = data.get("robot_x", 0)
                    ry = data.get("robot_y", 0)
                
                # Wrap grids in {"levels": ...} as expected by schema/frontend
                raw_threat = data.get("threat_levels")
                threat_grid = {"levels": raw_threat} if raw_threat else {}
                
                raw_obs = data.get("obstacles")
                obstacles = {"levels": raw_obs} if raw_obs else {}

                cs_x, cs_y = 0, 0
                cs_list = data.get("charging_stations")
                if cs_list and len(cs_list) > 0:
                    c1 = cs_list[0]
                    if isinstance(c1, list) or isinstance(c1, tuple):
                        cs_x, cs_y = c1[0], c1[1]
                
                # Prepare Multi-Agent 'robots' list
                robots_data = []
                if "robot_positions" in data:
                    raw_pos = data["robot_positions"]
                    raw_dir = data.get("robot_directions", [])
                    raw_bat = data.get("battery_levels", [])
                    raw_chg = data.get("is_charging_list", [])
                    
                    if isinstance(raw_pos, list):
                        for i, rp in enumerate(raw_pos):
                            # Extract x, y
                            if isinstance(rp, list):
                                x, y = rp[0], rp[1]
                            elif isinstance(rp, dict):
                                x, y = rp.get("x", 0), rp.get("y", 0)
                            else:
                                x, y = 0, 0
                                
                            # Extract other attributes safely
                            d = raw_dir[i] if isinstance(raw_dir, list) and i < len(raw_dir) else 0
                            b = raw_bat[i] if isinstance(raw_bat, list) and i < len(raw_bat) else 0.0
                            c = raw_chg[i] if isinstance(raw_chg, list) and i < len(raw_chg) else False
                            
                            robots_data.append({
                                "id": i,
                                "x": int(x),
                                "y": int(y),
                                "orientation": int(d),
                                "battery_percentage": float(b),
                                "is_charging": bool(c)
                            })
                
                # coverage_map typically also expects internal structure if present, but leaving as is for now if empty
                coverage_map = data.get("coverage_map", [])
                
                state = EnvironmentState(
                    session_id=job.id,
                    episode=episode,
                    step=step,
                    robot_x=rx,
                    robot_y=ry,
                    robot_orientation=orientation,
                    robots=robots_data if robots_data else None, # Populate robots column
                    threat_grid=threat_grid,
                    coverage_map=coverage_map, # Caution: might need structure too if not empty
                    obstacles=obstacles, # Added obstacles
                    suspicious_objects=data.get("suspicious_objects", []),
                    action_taken=data.get("action", 0),
                    reward_received=data.get("reward", 0.0),
                    battery_percentage=battery,
                    is_charging=False,
                    distance_to_charging_station=0.0,
                    charging_station_position_x=cs_x,
                    charging_station_position_y=cs_y
                )
                batch.append(state)
                
                if len(batch) >= batch_size:
                    db.add_all(batch)
                    await db.commit()
                    batch = []
                    
            except json.JSONDecodeError:
                continue
            except Exception as e:
                print(f"Error parsing line {idx}: {e}")
                continue

    if batch:
        db.add_all(batch)
        await db.commit()
        
    print(f"Import completed for {file_info['name']}")

async def main():
    async with AsyncSessionLocal() as db:
        try:
            for f in FILES:
                await import_file(db, f)
        except Exception as e:
            print(f"An error occurred: {e}")
            await db.rollback()
        finally:
            await db.close()

if __name__ == "__main__":
    asyncio.run(main())
