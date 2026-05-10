import os
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
        
    def chunk_and_store(self, document_text: str, document_id: str):
        """Phase 1: Ingestion. Turns text into vectors and uploads to Pinecone."""
        logger.info(f"Starting ingestion for document_id: '{document_id}'")
        
        chunks = document_text.split("\n\n")
        vectors_to_upload = []
        
        for i, chunk in enumerate(chunks):
            if len(chunk.strip()) < 10:
                continue 
                
            # Create the 384-dimension vector
            vector_values = self.embedder.encode(chunk).tolist()
            
            # Pinecone requires a unique ID for every single chunk
            chunk_id = f"doc_{document_id}_chunk_{i}"
            
            # We store the actual text in the "metadata" payload
            vectors_to_upload.append({
                "id": chunk_id,
                "values": vector_values,
                "metadata": {"text": chunk}
            })
            
        # Upload to the cloud in one batch
        if vectors_to_upload:
            logger.info(f"Uploading {len(vectors_to_upload)} vectorized chunks to Pinecone...")
            self.index.upsert(vectors=vectors_to_upload)
            logger.info(f"Success! Uploaded {len(vectors_to_upload)} chunks for document '{document_id}'.")
        else:
            logger.warning(f"No valid text chunks found to upload for document '{document_id}'.")

    def retrieve_context(self, user_question: str, top_k: int = 3) -> str:
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
