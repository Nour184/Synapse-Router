# Synapse-Router: Distributed RAG & Inference Orchestrator

Synapse-Router is a high-performance, distributed Retrieval-Augmented Generation (RAG) system. It features a custom Layer 7 edge proxy, GPU-accelerated compute nodes, and a robust circuit-breaking watchdog to ensure high availability for heavy AI workloads.

## 🚀 Key Features

- **Custom L7 Gateway:** OpenResty-based router with Round-Robin load balancing and "Smart Ban" circuit breaking.
- **Distributed Inference:** Multi-node GPU support using `llama-cpp-python` and CUDA acceleration.
- **Resilient RAG:** Accumulative document chunking and streaming vector synchronization with Pinecone.
- **Health Monitoring:** Real-time GPU telemetry and an automated watchdog for node recovery.
- **Async Ingestion:** Non-blocking document processing via FastAPI background tasks.

## 🏗️ Architecture Overview

The system is composed of several specialized tiers:

1.  **Gateway (OpenResty):** The entry point that tags requests, balances load, and manages node health states.
2.  **Compute Nodes (FastAPI + CUDA):** Workers that handle heavy LLM inference and document embedding.
3.  **Watchdog:** A monitoring daemon that identifies stalled nodes and manages the circuit breaker.
4.  **Admin Dashboard (Streamlit):** A UI for visualizing system metrics and node status.
5.  **Vector Store:** Cloud-hosted Pinecone index for semantic retrieval.

## 🛠️ Setup & Installation

### Prerequisites

- Docker & Docker Compose
- NVIDIA GPU with CUDA drivers (for compute nodes)
- Pinecone API Key
- HuggingFace Token (for model access)

### Environment Variables

Create a `.env` file in the root directory:

```env
HF_TOKEN=your_huggingface_token
PC_TOKEN=your_pinecone_api_key
```

### Deployment

To start the control plane (Gateway, Redis, Watchdog, Dashboard):
```bash
docker-compose --profile control up -d
```

To start the compute nodes:
```bash
docker-compose --profile compute up -d
```

## 📖 Usage

### Document Ingestion

Place your PDF in the `ingect/` directory and run the ingestion script:
```bash
cd ingect/
python ingect_script.py
```

### Inference API

Send prompts to the gateway:
```bash
curl -X POST http://localhost/api/chat \
     -H "Content-Type: application/json" \
     -d '{"prompt": "What is the theory of deep learning?"}'
```

### Monitoring

Access the Admin Dashboard at `http://localhost:8501`.

## 📂 Project Structure

- `gateway/`: Nginx configuration and Lua routing logic.
- `working-nodes/`: LLM runtime, RAG engine, and GPU monitoring code.
- `watchdog/`: Health check and recovery automation.
- `ingect/`: PDF parsing and ingestion tools.
- `admin/`: Streamlit-based telemetry dashboard.

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.
