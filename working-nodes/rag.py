import os
import time
import logging
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [RAG Engine] %(message)s'
)
logger = logging.getLogger(__name__)

class CloudRAGEngine:
    def __init__(self):
        logger.info("Initializing CloudRAGEngine...")
        
        pinecone_api_key = os.environ.get("PINECONE_API_KEY")
        
        if not pinecone_api_key:
            raise ValueError("PINECONE_API_KEY environment variable is missing! Please set it in your environment or docker-compose.yml.")
            
        logger.info("Connecting to Pinecone Cloud...")
        self.pc = Pinecone(api_key=pinecone_api_key)
        
        # Check if the index exists
        existing_indexes = [idx.name for idx in self.pc.list_indexes()]
        if "synapse-knowledge-base" not in existing_indexes:
            logger.error(f"Index 'synapse-knowledge-base' not found in your Pinecone project. Available indexes: {existing_indexes}")
            logger.info("Please create the index manually in the Pinecone console with dimension 384 and metric 'cosine'.")
            raise ValueError("Index 'synapse-knowledge-base' missing.")

        self.index = self.pc.Index("synapse-knowledge-base")
        logger.info("Successfully connected to Pinecone index: 'synapse-knowledge-base'")
        
        logger.info("Loading local embedding model (all-MiniLM-L6-v2)...")
        # Runs on CPU, outputs 384 dimensions
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("CloudRAGEngine initialization complete.")
        
    def chunk_and_store(self, document_text: str, document_id: str, batch_size: int = 100):
        logger.info(f"Starting accumulative ingestion for document_id: '{document_id}'")
        
        # 1. Break into raw paragraphs first
        raw_paragraphs = document_text.split("\n\n")
        
        built_chunks = []
        current_chunk = ""
        TARGET_CHUNK_SIZE = 1200  # Accumulate roughly 1,200 characters per vector slot
        
        # 2. Stitch fragments together into substantial contextual blocks
        for para in raw_paragraphs:
            cleaned_para = para.strip()
            if len(cleaned_para) < 5:
                continue
                
            if len(current_chunk) + len(cleaned_para) > TARGET_CHUNK_SIZE and current_chunk:
                built_chunks.append(current_chunk.strip())
                current_chunk = cleaned_para + "\n\n"
            else:
                current_chunk += cleaned_para + "\n\n"
                
        if current_chunk.strip():
            built_chunks.append(current_chunk.strip())

        vectors_to_upload = []
        
        # 3. Embed the substantial blocks
        for i, chunk in enumerate(built_chunks):
            vector_values = self.embedder.encode(chunk).tolist()
            chunk_id = f"doc_{document_id}_chunk_{i}"
            
            vectors_to_upload.append({
                "id": chunk_id,
                "values": vector_values,
                "metadata": {"text": chunk}
            })
            
        total_vectors = len(vectors_to_upload)
        
        if not vectors_to_upload:
            logger.warning(f"No valid text chunks found to upload for document '{document_id}'.")
            return

        logger.info(f"Prepared {total_vectors} vectorized chunks. Streaming to Pinecone in batches of {batch_size}...")
        
        # Slicing Loop: Process the array in controlled, network-safe bites
        for i in range(0, total_vectors, batch_size):
            # Slice out exactly 100 items (or the remainder)
            batch = vectors_to_upload[i : i + batch_size]
            
            try:
                logger.info(f"Upserting batch {i} to {i + len(batch)} of {total_vectors}...")
                self.index.upsert(vectors=batch)
                
                
            except Exception as e:
                logger.warning(f"Network stall on batch {i}. Executing fallback backoff wait...")
                time.sleep(3.0)  # Give the Pinecone gateway buffers a deep moment to clear
                
                # Forcefully retry the failed batch
                logger.info(f"Retrying batch {i} upsert...")
                self.index.upsert(vectors=batch)

        logger.info(f"Success! Fully completed batch streaming for document '{document_id}'.")

    def retrieve_context(self, user_question: str, top_k: int = 15) -> str:
        """Phase 2: Retrieval. Asks Pinecone for the most relevant chunks."""
        logger.info(f"Retrieving context for query: '{user_question}' (Fetching top {top_k} results)")
        
        # Turn the question into a vector
        query_vector = self.embedder.encode(user_question).tolist()
        
        # Ask Pinecone for the top matches
        logger.debug("Querying Pinecone index...")
        response = self.index.query(
            vector=query_vector,
            top_k=top_k,
            include_metadata=True
        )
        
        # Extract the text from the Pinecone response
        retrieved_chunks = [match["metadata"]["text"] for match in response["matches"]]
        logger.info(f"Successfully retrieved {len(retrieved_chunks)} relevant chunks from Pinecone.")
        
        return "\n---\n".join(retrieved_chunks)

# Initialize the engine
rag_instance = None
try:
    rag_instance = CloudRAGEngine()
except Exception as e:
    logger.critical(f"Failed to initialize RAG Engine: {e}")
