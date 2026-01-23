
import sys
import os
from sqlalchemy import text, inspect
from dotenv import load_dotenv

sys.path.append(os.getcwd())
load_dotenv()
if os.getenv('DATABASE_URL'):
    os.environ['DATABASE_URL'] = os.getenv('DATABASE_URL').replace("@postgres:", "@localhost:")

from app.db.database import sync_engine

def inspect_cols():
    inspector = inspect(sync_engine)
    columns = inspector.get_columns("trainingmetric")
    print(f"Columns in trainingmetric: {len(columns)}")
    for col in columns:
        print(f"  {col['name']}")

if __name__ == "__main__":
    inspect_cols()
