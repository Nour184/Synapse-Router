#dummy node.py for testing before using a mesh vpn as tailscale
from fastapi import FastAPI, Request

app = FastAPI()

@app.api_route("/api/", methods=["GET", "POST"])
async def catch_all(request: Request):
    # get the header that NGINX Lua script injected!
    req_id = request.headers.get("x-request-id", "No ID Found")
    
    return {
        "status": "success",
        "message": "Traffic successfully reached the Python worker!",
        "injected_id_received": req_id
    }