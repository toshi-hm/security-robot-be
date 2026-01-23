
import sys
import os
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

sys.path.append(os.getcwd())
env_path = os.path.join(os.getcwd(), '.env')
load_dotenv(env_path)

if os.getenv('DATABASE_URL'):
    os.environ['DATABASE_URL'] = os.getenv('DATABASE_URL').replace("@postgres:", "@localhost:")

from app.db.database import sync_engine

with sync_engine.connect() as conn:
    print("trainingjob columns:", pd.read_sql(text('SELECT * FROM trainingjob LIMIT 1'), conn).columns.tolist())
