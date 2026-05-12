echo "Installing Hugging Face CLI..."
pip install -U "huggingface_hub[cli]"

echo "Creating Models Directory"
mkdir -pv ./models

echo "Downloading Llama-3.2-1B-Instruct GGUF..."

hf download \
  bartowski/Llama-3.2-1B-Instruct-GGUF \
  Llama-3.2-1B-Instruct-Q4_K_M.gguf \
  --local-dir ./models \
  --token $HF_TOKEN

echo "Download Complete."


