FROM python:3.11-slim

WORKDIR /app

# Install Docker CLI so we can execute iptables inside the gateway
RUN apt-get update && apt-get install -y docker.io iptables && rm -rf /var/lib/apt/lists/*

COPY required_libraries.txt .
RUN pip install --no-cache-dir -r required_libraries.txt

COPY watchdog.py .

# Run the script unbuffered so print() statements show up instantly in Docker logs
CMD ["python", "-u", "watchdog.py"]