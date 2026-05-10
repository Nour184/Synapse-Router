from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
import asyncio
import socket
import uvicorn
import time
from llm import llm_instance
from rag import rag_instance
import logging

app = FastAPI()

# ---------------------------------------------------------
# CUSTOM LOGGING CONFIGURATION
# ---------------------------------------------------------
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "%(levelprefix)s %(asctime)s | %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",  # Forces output to stdout so Docker catches it
        },
    },
    "loggers": {
        "uvicorn": {"handlers": ["default"], "level": "INFO"},
        "uvicorn.error": {"level": "INFO"},
        "uvicorn.access": {"handlers": ["default"], "level": "INFO", "propagate": False},
    },
} 

# Hook into the custom uvicorn error logger so our manual logs match the format
logger = logging.getLogger("uvicorn.error")

# Define the expected JSON structure for uploading documents
class DocumentPayload(BaseModel):
    document_id: str
    text: str

# ---------------------------------------------------------
# PHASE 1: INGESTION (Must be defined BEFORE the catch-all)
# ---------------------------------------------------------
@app.api_route("/api/ingest", methods=["POST"])
async def ingest_document(payload: DocumentPayload):
    logger.info(f"Received ingestion request for document: {payload.document_id}")
    
    try:
        start_time = time.time()
        
        if not rag_instance:
            raise Exception("RAG Engine is not initialized. Check server logs for details.")

        # Call the Pinecone logic from rag.py
        rag_instance.chunk_and_store(
            document_text=payload.text, 
            document_id=payload.document_id
        )
        
        elapsed_time = time.time() - start_time
        logger.info(f"Ingestion complete for {payload.document_id} in {elapsed_time:.2f}s")
        
        return {
            "status": "success",
            "message": f"Successfully vectorized and stored document '{payload.document_id}'",
            "processing_time": round(elapsed_time, 2)
        }
        
    except Exception as e:
        logger.error(f"Ingestion failed for document {payload.document_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ---------------------------------------------------------
# PHASE 2: INFERENCE CATCH-ALL
# By adding {full_path:path}, this will catch /api/, /api/generate, /api/chat, etc.
# ---------------------------------------------------------
@app.api_route("/api/{full_path:path}", methods=["GET", "POST"])
async def catch_all(request: Request, full_path: str = ""):
    # 1. Get the header that NGINX Lua script injected!
    req_id = request.headers.get("x-request-id", "No ID Found")
    
    # 2. Get the Docker container ID to prove load balancing works
    worker_name = socket.gethostname()
    
    try:
        payload = await request.json()
        user_prompt = payload.get("prompt", "")
    except Exception as e:
        logger.error(f"[{req_id}] Failed to parse JSON payload: {e}")
        return {"status": "error", "message": "Invalid JSON payload."}

    if not user_prompt:
        return {"status": "error", "message": "No prompt provided in the request."}

    logger.info(f"[{req_id}] Received inference request on {worker_name}.")
    start_time = time.time()
    
    # 3. --- THE RAG PIPELINE ---
    
    # STEP A: RETRIEVE
    logger.info(f"[{req_id}] Asking Pinecone for relevant context...")
    
    if not rag_instance:
        logger.warning(f"[{req_id}] RAG Engine not initialized. Proceeding WITHOUT context.")
        context = "No context available (RAG initialization failed)."
    else:
        context = rag_instance.retrieve_context(user_prompt, top_k=3)
    
    # STEP B: AUGMENT
    augmented_prompt = f"""You are a highly precise technical assistant. Use ONLY the following retrieved context to answer the user's question. 
If the answer is not contained within the context, you must state that you do not have enough information. Do not guess.

=== RETRIEVED CONTEXT ===
{context}

=== USER QUESTION ===
{user_prompt}
"""

    # STEP C: GENERATE
    logger.info(f"[{req_id}] Context retrieved. Forwarding augmented prompt to Llama model...")
    llm_response = llm_instance.generate(augmented_prompt)

    elapsed_time = time.time() - start_time
    logger.info(f"[{req_id}] Processing complete in {elapsed_time:.2f}s.")
    
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
    uvicorn.run(app, host="0.0.0.0", port=5000, log_config=LOGGING_CONFIG)
