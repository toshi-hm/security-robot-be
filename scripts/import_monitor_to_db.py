"""
# 内容
実験結果データ(CSV/JSONL)をデータベース(PostgreSQL)にインポートするスクリプト。
FrontendのPlayback機能で結果を可視化・再生するために必要。

# どこで何のために必要なのか
- データ連携: 実験スクリプトで生成されたローカルの結果ファイルを、Webアプリから参照可能な形式(DB)に変換・格納する。
- 実行場所: `security-robot-be` ルートディレクトリ
- コマンド: `python scripts/import_monitor_to_db.py`

# 入力データ・ファイル
- `monitor_n{N}.monitor.csv`: 学習ログ
- `trajectory_n{N}.jsonl`: 軌跡ログ

# 出力データ・ファイル
- DBテーブルへのINSERT:
  - `trainingjob`: ジョブ管理レコード
  - `trainingmetric`: 学習曲線データ
  - `environmentstate`: ステップごとの状態データ（Playback用）
"""

import asyncio
import os
import sys
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add app to path
sys.path.append(os.getcwd())

# Set DB URL for script
# Use asyncpg scheme so app.db.database._resolve_sync_driver maps it to 'psycopg' (v3)
os.environ["DATABASE_URL"] = "postgresql+asyncpg://security_robot:change_me@localhost:5432/security_robot"

import json
from app.models.training import TrainingJob, TrainingMetric, TrainingAlgorithm, TrainingJobStatus
from app.models.environment import EnvironmentState, EnvironmentDefinition
from app.db.session import SessionLocal

def import_experiment(num_robots: int):
    filename = f"monitor_n{num_robots}.monitor.csv"
    if not os.path.exists(filename):
        print(f"Skipping N={num_robots} (File not found: {filename})")
        return

    print(f"Importing N={num_robots} from {filename}...")
    
    # Read CSV (skip header line 1)
    df = pd.read_csv(filename, skiprows=1)
    
    # Map columns
    # Monitor CSV: r, l, t, coverage_ratio, average_threat_level
    if 'r' not in df.columns or 'l' not in df.columns:
        print(f"Error: Invalid CSV format for N={num_robots}")
        return

    # Calculate actual timestep (cumulative sum of lengths)
    df['timestep_calculated'] = df['l'].cumsum()

    session = SessionLocal()
    try:
        # 1. Create Job
        job_name = f"Thesis Experiment (N={num_robots}) - Impt {datetime.now().strftime('%H:%M')}"
        
        job = TrainingJob(
            name=job_name,
            algorithm=TrainingAlgorithm.ppo,
            status=TrainingJobStatus.completed,
            environment_type="standard",
            env_width=20,
            env_height=20,
            num_robots=num_robots,
            total_timesteps=int(df['timestep_calculated'].max()),
            current_timestep=int(df['timestep_calculated'].max()),
            episodes_completed=len(df),
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            config={"config": {"revisit_window": 100}} # Thesis config
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        print(f"Created Job ID: {job.id} ({job_name})")

        # 2. Create Metrics
        metrics = []
        for idx, row in df.iterrows():
            metric = TrainingMetric(
                job_id=job.id,
                timestep=int(row['timestep_calculated']),
                episode=idx + 1,
                reward=float(row['r']),
                coverage_ratio=float(row.get('coverage_ratio', 0.0)),
                threat_level_avg=float(row.get('average_threat_level', 0.0)),
                exploration_score=0.0, # Not in monitor
                timestamp=datetime.utcnow()
            )
            metrics.append(metric)
        
        session.add_all(metrics)
        session.commit()
        print(f"Imported {len(metrics)} metrics for Job {job.id}")
        
        # 3. Create Environment States (Trajectories)
        traj_filename = f"trajectory_n{num_robots}.jsonl"
        if os.path.exists(traj_filename):
            print(f"Importing trajectories from {traj_filename}...")
            states = []
            
            with open(traj_filename, 'r') as f:
                for line in f:
                    data = json.loads(line)
                    
                    # Map JSON to EnvironmentState
                    # JSON: robot_x, robot_y, robot_positions, robot_directions, battery_levels, is_charging_list, threat_levels, obstacles
                    
                    # Correct Episode ID (4000 steps per episode)
                    current_step = data.get('step', 0)
                    inferred_episode = (current_step // 4000) + 1
                    
                    state = EnvironmentState(
                        session_id=job.id, # Fixed: Model uses session_id FK
                        episode=inferred_episode,
                        step=current_step,
                        
                        # Primary robot (compatibility)
                        robot_x=data.get('robot_x', 0),
                        robot_y=data.get('robot_y', 0),
                        robot_orientation=data.get('robot_directions', [0])[0] if data.get('robot_directions') else 0,
                        
                        # Full state
                        robots=[{
                            "id": i, 
                            "x": pos[0], 
                            "y": pos[1], 
                            "orientation": data.get('robot_directions', [])[i] if i < len(data.get('robot_directions', [])) else 0,
                            "battery_percentage": data.get('battery_levels', [])[i] if i < len(data.get('battery_levels', [])) else 100
                        } for i, pos in enumerate(data.get('robot_positions', []))],
                        
                        charging_stations=[{"x": cs[0], "y": cs[1]} for cs in data.get('charging_stations', [])] if data.get('charging_stations') else [],
                        threat_grid=data.get('threat_levels'),
                        obstacles=data.get('obstacles'),
                        coverage_map=None, # Not captured to save space
                        suspicious_objects=[],
                        
                        coverage_ratio=data.get('coverage_ratio'),
                        battery_percentage=data.get('battery_levels', [0])[0] if data.get('battery_levels') else 0, # Primary robot
                        is_charging=data.get('is_charging_list', [False])[0] if data.get('is_charging_list') else False, # Primary robot
                    )
                    states.append(state)
                    
                    # Batch commit to avoid memory usage
                    if len(states) >= 1000:
                        session.add_all(states)
                        session.commit()
                        states = []
            
            # Commit remaining
            if states:
                session.add_all(states)
                session.commit()
            print(f"Imported trajectory states for Job {job.id}")
        else:
            print(f"Warning: No trajectory file found: {traj_filename}")
        
    except Exception as e:
        session.rollback()
        print(f"Error importing N={num_robots}: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Import specific N
        n = int(sys.argv[1])
        import_experiment(n)
    else:
        # Import all
        for n in [1, 2, 3, 4]:
            import_experiment(n)
