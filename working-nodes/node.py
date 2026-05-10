from fastapi import FastAPI, Request
import asyncio
import socket
import uvicorn

app = FastAPI()

print("WORKER STARTING UP...")

# By adding {full_path:path}, this will catch /api/, /api/generate, /api/chat, etc.
@app.api_route("/api/{full_path:path}", methods=["GET", "POST"])
async def catch_all(request: Request, full_path: str = ""):
    # 1. Get the header that NGINX Lua script injected!
    req_id = request.headers.get("x-request-id", "No ID Found")
    
    # 2. Get the Docker container ID to prove load balancing works
    worker_name = socket.gethostname()
    
    # 3. Simulate a 1-second delay for "inference"
    await asyncio.sleep(5)
    
    # 4. Return the response back to Nginx
    return {
        "status": "success",
        "message": "Traffic successfully reached the Python worker!",
        "handled_by_container": worker_name,
        "injected_id_received": req_id,
        "path_received": f"/api/{full_path}"
    }

if __name__ == "__main__":
    # Ensure it binds to 0.0.0.0 so Nginx can reach it from outside the container
    uvicorn.run(app, host="0.0.0.0", port=5000)