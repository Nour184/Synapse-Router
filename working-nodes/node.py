from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from pydantic import BaseModel
import asyncio
import socket
import uvicorn
from contextlib import asynccontextmanager

from rag import rag_instance
from llm import llm_instance

import logging

import subprocess
import os
import threading
import time 

from collections import deque

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
        "uvicorn.error": {"handlers": ["default"], "level":"INFO", "propagate":False},
        "uvicorn.access": {"handlers": ["default"], "level": "INFO", "propagate": False},
    },
} 

# Hook into the custom uvicorn error logger so our manual logs match the format
logger = logging.getLogger("uvicorn.error")

stop_monitor_event = threading.Event()
gpu_history = deque(maxlen=30)

def gpu_monitor():
    current_pid = os.getpid()

    docker_service_name = os.getenv('SERVICE_NAME', "UNKNOWN_SERVICE")
    
    while not stop_monitor_event.is_set():
       try:
           output = subprocess.check_output(
                   ["nvidia-smi", "pmon", "-c", "1"],
                   encoding='utf-8'
                   ).splitlines()
           
           for line in output:
               parts = line.split()
               if len(parts) >= 4 and parts[1].isdigit():
                   pid = int(parts[1])
                   if pid == current_pid:
                       gpu_util = parts[3]
                       gpu_util = 0 if gpu_util == '-' else int(gpu_util)
                       logger.info(f"[{docker_service_name}] GPU Utilization {gpu_util}")
                       gpu_history.append({"time": time.strftime("%H:%M:%S"), "Node": docker_service_name,"utilization": gpu_util})
       except Exception as e:
           logger.error(f"[{docker_service_name}] Failed to measure utilization")

       time.sleep(1.0) # sample time 1 second


# Define the expected JSON structure for uploading documents
class DocumentPayload(BaseModel):
    document_id: str
    text: str

# Define the expected JSON for querying
class PromptPayload(BaseModel):
    prompt: str

inference_queue: asyncio.Queue = None

# ------------------------------------------------------------------
# async context manager - used to initialize queue and worker thread
# ------------------------------------------------------------------
@asynccontextmanager
async def lifespan_manager(app: FastAPI):
    global inference_queue
    inference_queue = asyncio.Queue(maxsize=100)

    worker_thread = asyncio.create_task(inference_worker())
    monitor_thread = threading.Thread(target=gpu_monitor, daemon=True)
    monitor_thread.start()

    yield # Is Inference Catch all higher priority?

    stop_monitor_event.set()
    worker_thread.cancel()
    logger.info("worker thread cleanly shut down.")

# Initialize Fast API with the life span controller
app = FastAPI(lifespan = lifespan_manager)

@app.api_route('/api/health', methods=['GET'])
def health_check():
    return {"status": "ok", "message": "Node is healthy"}

@app.get("/api/metrics")
def get_node_metrics():
    return {"history": list(gpu_history)}


# ---------------------------------------------------------
# PHASE 1: INGESTION 
# ---------------------------------------------------------
@app.api_route("/api/ingest", methods=["POST"])
async def ingest_document(payload: DocumentPayload, background_tasks: BackgroundTasks):
    logger.info(f"Received massive ingestion payload for document: {payload.document_id}")
    
    if not rag_instance:
        raise HTTPException(status_code=500, detail="RAG Engine offline. Check logs.")

    # 1. Hand the heavy synchronous chunking/embedding pipeline entirely to the background queue.
    # Execution detaches completely from the open HTTP socket!
    background_tasks.add_task(
        rag_instance.chunk_and_store,
        document_text=payload.text, 
        document_id=payload.document_id
    )
    
    # 2. Instantly drop the TCP connection and return a clean 202 Accepted state
    return {
        "status": "processing",
        "message": f"Successfully queued '{payload.document_id}' (1.87M chars) for detached background vectorization.",
        "estimated_completion_time_minutes": 5
    }

# ---------------------------------
# Blocking function used in phase 2
# ---------------------------------

def run_heavy_inference(prompt: str, req_id: str, top_k: int = 3) -> str:
    """Executes heavy blocking network I/O and CUDA operations entirely outside the GIL."""
    # STEP A: RETRIEVE
    logger.info(f"[{req_id}] Asking Pinecone for relevant context...")
    if not rag_instance:
        logger.warning(f"[{req_id}] RAG Engine off. Proceeding WITHOUT context.")
        context = "No context available."
    else:
        context = rag_instance.retrieve_context(prompt, top_k=top_k)
    
    # STEP B: AUGMENT
    augmented_prompt = f"""You are an expert AI Engineering professor. Your task is to answer the user's question by applying the technical theory from the retrieved context.

=== INSTRUCTIONS ===
1. THEORY & FORMULAS: You must ground all theoretical explanations, algorithms, and mathematical definitions strictly in the provided context.
2. EXAMPLES: If the user requests a concrete numeric example, code snippet, or analogy to understand the theory, and one is not explicitly present in the context, you are authorized to construct a precise, mathematically correct example to demonstrate the retrieved concepts.
3. If the core theoretical concept itself is entirely missing from the context, state that you lack the context to answer.

=== RETRIEVED CONTEXT ===
{context}

=== USER QUESTION ===
{prompt}
"""

    # STEP C: GENERATE
    logger.info(f"[{req_id}] Forwarding augmented prompt to Llama model on RTX 2060...")
    return llm_instance.generate(augmented_prompt)


# ---------------------------------------------------------
# PHASE 2: INFERENCE CATCH-ALL (The Producer)
# ---------------------------------------------------------

# ---------------------------------------------------------
# THE CONSUMER (Background GPU Worker Task)
# ---------------------------------------------------------
async def inference_worker():
    """Runs continuously in the background, pulling requests 1-by-1 to feed the GPU safely."""
    logger.info("Background GPU Consumer Task successfully booted and waiting for work.")
    while True:
        # Safely pause background loop until a payload enters the queue
        req_id, request, prompt, future = await inference_queue.get()
        
        try:
            # GUARDRAIL 1: Ghost Compute Shield
            # Check if the user dropped their connection while waiting in the queue buffer
            if await request.is_disconnected():
                logger.warning(f"[{req_id}] Client disconnected mid-queue. Dropping task. Saving RTX 2060 VRAM!")
                # Clear inference Queue as this node is already banned and requests are re-routed
                while not inference_queue.empty():
                    inference_queue.get_nowait()
                    inference_queue.task_done()
                if not future.done():
                    # Resolving with a 499 (Client Closed Request) wakes the frame cleanly
                    future.set_exception(HTTPException(status_code=499, detail="Client Closed Request"))
                continue

            logger.info(f"[{req_id}] Acquired GPU slot. Offloading compute to OS thread pool...")
            
            # Offload heavy synchronous pipeline completely outside the web event loop
            answer = await asyncio.to_thread(run_heavy_inference, prompt, req_id)
            
            # Wakes up the suspended endpoint coroutine frame sitting in Heap RAM
            if not future.done():
                future.set_result(answer)
                
        except Exception as e:
            logger.error(f"[{req_id}] Fatal error during GPU inference processing: {e}")
            if not future.done():
                future.set_exception(HTTPException(status_code=500, detail=f"Internal Inference Error: {str(e)}"))
        finally:
            # Tell the queue state machine this exact task token is fully completed
            inference_queue.task_done()

@app.api_route("/api/{full_path:path}", methods=["POST"])
async def catch_all(request: Request, payload: PromptPayload, full_path: str = ""):
    req_id = request.headers.get("x-request-id", "No ID Found")
    worker_name = socket.gethostname()
    
    
    if inference_queue.full():
        logger.warning(f"[{req_id}] Node queue full (100 active tasks). Instantly shedding load!")
        # Raising an instant 503 forces NGINX to cleanly Round-Robin to the next idle node
        raise HTTPException(status_code=503, detail="Worker node at maximum queue capacit.//lly.")

    logger.info(f"[{req_id}] Ingesting prompt on {worker_name}. Pushing to internal queue...")
    start_time = time.time()
    
    # Create an empty, dumb state-machine ticket for this specific request
    pending_future = asyncio.Future()
    
    inference_queue.put_nowait((req_id, request, payload.prompt, pending_future))
    
    try:
        # COOPERATIVE YIELD: Detach this coroutine frame to Heap RAM and free the web loop
        # The connection stays perfectly open while Uvicorn handles concurrent traffic
        llm_response = await pending_future
    except HTTPException as http_exc:
        # Cleanly re-raise specific HTTP exceptions injected by the background worker (like 499)
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unexpected error resolving inference future.")

    elapsed_time = time.time() - start_time
    logger.info(f"[{req_id}] Processing complete in {elapsed_time:.2f}s. Shipping response.")
    
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
