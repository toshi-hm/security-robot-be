import os
import sqlite3

db_path = "security_robot.db"
if not os.path.exists(db_path):
  print(f"Error: {db_path} does not exist in {os.getcwd()}")
else:
  try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"Tables in {db_path}:")
    for t in tables:
      print(f"- {t[0]}")
    conn.close()
  except Exception as e:
    print(f"Error reading DB: {e}")
