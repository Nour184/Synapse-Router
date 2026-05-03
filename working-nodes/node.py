from fastapi import FastAPI, Request
import asyncio
import socket
import uvicorn
import time
from llm import llm_instance

app = FastAPI()

print("WORKER STARTING UP...")

# By adding {full_path:path}, this will catch /api/, /api/generate, /api/chat, etc.
@app.api_route("/api/{full_path:path}", methods=["GET", "POST"])
async def catch_all(request: Request, full_path: str = ""):
    # 1. Get the header that NGINX Lua script injected!
    req_id = request.headers.get("x-request-id", "No ID Found")
    
    # 2. Get the Docker container ID to prove load balancing works
    worker_name = socket.gethostname()
    
    # 3. call the model for inference 
    payload = await request.json()
    user_prompt = payload.get("prompt", "NO PROMPT IS PROVIDED RETURN WHAT IS YOUR QUESTION")

    start_time = time.time()

    llm_response = llm_instance.generate(user_prompt)

    elapsed_time = time.time() - start_time

    
    # 4. Return the response back to Nginx
    return {
        "status": "success",
        "handled_by_container": worker_name,
        "injected_id_received": req_id,
        "path_received": f"/api/{full_path}",
        "processing_time": round(elapsed_time, 2),
        "response": llm_response
    }

if __name__ == "__main__":
    # Ensure it binds to 0.0.0.0 so Nginx can reach it from outside the container
    uvicorn.run(app, host="0.0.0.0", port=5000)
