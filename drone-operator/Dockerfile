FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY operator.py .

CMD ["kopf", "run", "/app/operator.py", "--all-namespaces"]
