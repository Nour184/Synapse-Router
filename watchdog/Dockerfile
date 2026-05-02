FROM python:3.11-slim

WORKDIR /app

COPY required_libraries.txt .
RUN pip install --no-cache-dir -r required_libraries.txt

COPY watchdog.py .

# Run the script unbuffered so print() statements show up instantly in Docker logs
CMD ["python", "-u", "watchdog.py"]