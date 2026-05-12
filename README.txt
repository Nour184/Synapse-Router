Synapse-Router: Distributed RAG & Inference Orchestrator
========================================================

Synapse-Router is a distributed system designed for scalable AI inference 
and Retrieval-Augmented Generation (RAG).

QUICK START:
-----------
1. Configure .env with HF_TOKEN and PC_TOKEN.
2. Run `docker-compose --profile control up -d` to start the gateway.
3. Run `docker-compose --profile compute up -d` to start compute nodes.
4. Access the dashboard at http://localhost:8501.

CORE COMPONENTS:
---------------
- Gateway: OpenResty/Nginx L7 Router (Port 80)
- Workers: FastAPI + CUDA Compute Nodes (Port 5000-5002)
- Watchdog: Automated health monitoring & recovery.
- Admin: Streamlit telemetry dashboard (Port 8501).

API ENDPOINTS:
-------------
- POST /api/ingest : Document vectorization.
- POST /api/chat   : Context-aware LLM inference.
- GET /api/metrics : Local node GPU telemetry.

For detailed documentation, refer to README.md.
