FROM python:3.10-slim

WORKDIR /myFirstDockerApp

COPY required_libraries.txt .

RUN pip install --no-cache-dir -r required_libraries.txt

COPY . .

CMD ["uvicorn", "node:app", "--host", "0.0.0.0", "--port", "8000"]