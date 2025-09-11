import os
import time
import random
import psycopg2

DRONE_ID = os.environ.get("DRONE_ID")
DB_HOST = os.environ.get("POSTGRES_HOST")
DB_NAME = os.environ.get("POSTGRES_DB")
DB_USER = os.environ.get("POSTGRES_USER")
DB_PASSWORD = os.environ.get("POSTGRES_PASSWORD")
DURATION = 15

conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print(f"[{DRONE_ID}] Starting coordinate collection for {DURATION} seconds.")
start_time = time.time()
while time.time() - start_time < DURATION:
    lat = random.uniform(25.0, 25.2)
    lon = random.uniform(121.4, 121.6)
    print(f"[{DRONE_ID}] Logging coordinates: ({lat:.6f}, {lon:.6f})")
    cur.execute(
        "INSERT INTO coordinates (drone_id, latitude, longitude) VALUES (%s, %s, %s)",
        (DRONE_ID, lat, lon)
    )
    conn.commit()
    time.sleep(1)

cur.close()
conn.close()
print(f"[{DRONE_ID}] Coordinate collection finished.")