import argparse
import pandas as pd
from sqlalchemy import create_engine
from app.core.config import settings
from app.models.training import TrainingMetric, TrainingJob
import matplotlib.pyplot as plt

def analyze(job_id: int):
    # Connect
    url = str(settings.database_url)
    # Convert asyncpg to psycopg for sync usage with pandas
    if "asyncpg" in url:
        url = url.replace("asyncpg", "psycopg")
    
    print(f"Connecting to: {url}")
    engine = create_engine(url)


    print(f"Analyzing Job {job_id}...")
    
    # Check if job exists
    # We can use direct SQL
    try:
        metrics = pd.read_sql(f"SELECT * FROM trainingmetric WHERE job_id = {job_id} ORDER BY timestep ASC", engine)
    except Exception as e:
        # Fallback to defaults
        # Assume DATABASE_URL env var or settings default
        url = "postgresql+psycopg://security_robot:change_me@localhost:5432/security_robot"
        engine = create_engine(url)
        metrics = pd.read_sql(f"SELECT * FROM trainingmetric WHERE job_id = {job_id} ORDER BY timestep ASC", engine)

    if metrics.empty:
        print("No metrics found.")
        return

    print(f"Found {len(metrics)} data points.")
    print("Summary:")
    print(metrics[['reward', 'coverage_ratio', 'exploration_score']].describe())
    
    # Last 10 average
    last_10 = metrics.tail(10)
    avg_reward = last_10['reward'].mean()
    avg_cov = last_10['coverage_ratio'].mean()
    
    print(f"\nFinal Performance (Last 10 avg):")
    print(f"Reward: {avg_reward:.4f}")
    print(f"Coverage: {avg_cov:.4f}")

    return avg_reward, avg_cov

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("job_id", type=int)
    args = parser.parse_args()
    analyze(args.job_id)
