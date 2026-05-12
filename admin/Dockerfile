FROM python:3.11-slim

WORKDIR /app
COPY required_libraries.txt .
RUN pip install --no-cache-dir -r required_libraries.txt

COPY admin-dashboard.py .

#expose streamlit default port
EXPOSE 8501 

CMD ["streamlit", "run", "admin-dashboard.py", "--server.port=8501", "--server.address=0.0.0.0"]