import os
import time
import random
import psycopg2

DRONE_ID = os.environ.get("DRONE_ID")
DB_HOST = os.environ.get("POSTGRES_HOST")
DB_NAME = os.environ.get("POSTGRES_DB")
DB_USER = os.environ.get("POSTGRES_USER")
DB_PASSWORD = os.environ.get("POSTGRES_PASSWORD")
DURATION = 5

conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

battery_level = float(random.randint(90, 100))
print(f"[{DRONE_ID}] Starting battery logging for {DURATION} seconds. Initial level: {battery_level:.2f}%")
start_time = time.time()
while time.time() - start_time < DURATION:
    print(f"[{DRONE_ID}] Logging battery: {battery_level:.2f}%")
    cur.execute(
        "INSERT INTO battery_logs (drone_id, battery_level) VALUES (%s, %s)",
        (DRONE_ID, battery_level)
    )
    conn.commit()
    battery_level -= 0.1
    time.sleep(1)

cur.close()
conn.close()
print(f"[{DRONE_ID}] Battery logging finished.")