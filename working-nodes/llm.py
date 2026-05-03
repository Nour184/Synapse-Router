from llama_cpp import Llama

class LlamaEngine:

    def __init__(self, model_path: str = "./models/Llama-3.2-1B-Instruct-Q4_K_M.gguf"):
        # This call blocks the thread until the entire model is loaded in memory
        self.llm = Llama(
                model_path = model_path,
                n-gpu-layers=-1,
                n_ctx = 2048, # 2MB,
                n_threads = 4,
                verbose = False
                )

    def generate(self, user_prompt: str) -> str:
        # Llama 3.x strictly requires this specific prompt formatting structure to work
        formatted_prompt = (
            "<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\n"
            f"{user_prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
        )

        output = self.llm(
            formatted_prompt,
            max_tokens=256,
            stop=["<|eot_id|>"], # Tells the model to stop generating when the turn is over
            echo=False
        )
        
        return output["choices"][0]["text"].strip()

# Initialize a singleton instance to be imported by the router
llm_instance = LlamaEngine()
