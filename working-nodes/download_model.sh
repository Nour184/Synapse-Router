echo "Installing Hugging Face CLI..."
pip install -U "huggingface_hub[cli]"

echo "Creating Models Directory"
mkdir -pv ./models

echo "Downloading Llama3.2-1B-Instruct-GGUF in ./models..."
huggingface-cli download \
	bartowski/Llama-3.2-1B-Instruct-GGUF \
	--include "Llama-3.2-1B-Instruct-Q4_K_M.gguf" \
	--local-dir ./models

echo "Download Complete."


