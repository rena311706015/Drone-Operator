FROM python:3.11-slim

RUN apt-get update && apt-get install -y postgresql-client && rm -rf /var/lib/apt/lists/*
RUN pip install psycopg2-binary

WORKDIR /app
COPY health_check.py .
COPY collect_coords.py .
COPY collect_battery.py .

RUN chmod +x *.py