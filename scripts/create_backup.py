from datetime import datetime
import json
from pathlib import Path
import shutil
import tarfile

import requests

# Configuration
API_BASE = "http://localhost:8000/api/v1"
BACKUP_DIR = Path("backups")
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP_ROOT = BACKUP_DIR / f"backup_{TIMESTAMP}"
DATA_DIR = BACKUP_ROOT / "data"
MODELS_DIR = BACKUP_ROOT / "models"
LOGS_DIR = BACKUP_ROOT / "logs"

def fetch_all_sessions():
    print("Fetching sessions from API...")
    try:
        # Fetch list (handle pagination if necessary, but starting with large limit)
        resp = requests.get(f"{API_BASE}/training/list?page_size=100")
        resp.raise_for_status()
        data = resp.json()
        return data.get("sessions", [])
    except Exception as e:
        print(f"Error fetching sessions: {e}")
        return []

def fetch_session_metrics(session_id):
    metrics = []
    page = 1
    page_size = 500

    while True:
        try:
            url = (
                f"{API_BASE}/training/sessions/{session_id}/metrics"
                f"?page={page}&page_size={page_size}"
            )
            resp = requests.get(url)
            resp.raise_for_status()
            data = resp.json()

            batch = data.get("metrics", [])
            if not batch:
                break

            metrics.extend(batch)

            # Check if we've fetched everything
            total = data.get("total", 0)
            if len(metrics) >= total or len(batch) < page_size:
                break

            page += 1

        except Exception as e:
            print(f"Error fetching metrics page {page} for session {session_id}: {e}")
            break

    return metrics

def export_api_data():
    print("Exporting Database Data via API...")
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    sessions = fetch_all_sessions()
    print(f"Found {len(sessions)} sessions.")

    export_data = {
        "sessions": [],
        "exported_at": datetime.now().isoformat()
    }

    for session in sessions:
        sid = session["id"]
        # metrics = fetch_session_metrics(sid) # Optional: Include metrics in dump?
        # Including metrics makes the dump self-contained for easy restore
        metrics = fetch_session_metrics(sid)

        session_dump = session.copy()
        session_dump["metrics"] = metrics
        export_data["sessions"].append(session_dump)
        print(f"  Exported Session {sid}: {session['name']} ({len(metrics)} metrics)")

    dump_file = DATA_DIR / "db_export.json"
    with open(dump_file, "w") as f:
        json.dump(export_data, f, indent=2)
    print(f"Database dump saved to {dump_file}")

def backup_local_files():
    print("Backing up local artifacts...")
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Models
    source_models = Path("models")
    if source_models.exists():
        for model_file in source_models.glob("*.pth"):
            shutil.copy2(model_file, MODELS_DIR)
            print(f"  Backed up model: {model_file.name}")

    # 2. Result Logs (Cycle 11/12 JSONL)
    source_logs = Path("report/result")
    if source_logs.exists():
        for log_file in source_logs.glob("*.jsonl"):
            shutil.copy2(log_file, LOGS_DIR)
            print(f"  Backed up log: {log_file.name}")

def create_archive():
    archive_name = BACKUP_DIR / f"security_robot_backup_{TIMESTAMP}.tar.gz"
    print(f"Creating archive {archive_name}...")

    with tarfile.open(archive_name, "w:gz") as tar:
        tar.add(BACKUP_ROOT, arcname=BACKUP_ROOT.name)

    print(f"Backup archive created successfully: {archive_name}")

    # Cleanup temporary directory
    shutil.rmtree(BACKUP_ROOT)
    return archive_name

def main():
    try:
        # Create temp structure
        BACKUP_ROOT.mkdir(parents=True, exist_ok=True)

        # 1. Export DB Data
        export_api_data()

        # 2. Backup Files
        backup_local_files()

        # 3. Archive
        archive_path = create_archive()

        print("\n" + "=" * 50)
        print("BACKUP COMPLETE")
        print(f"File: {archive_path}")
        print("=" * 50)

    except Exception as e:
        print(f"Backup failed: {e}")
        # Clean up if possible
        if BACKUP_ROOT.exists():
            shutil.rmtree(BACKUP_ROOT)

if __name__ == "__main__":
    main()
