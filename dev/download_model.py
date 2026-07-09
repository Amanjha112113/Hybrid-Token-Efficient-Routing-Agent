#!/usr/bin/env python3
import os
from huggingface_hub import hf_hub_download

def download_model():
    model_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
    os.makedirs(model_dir, exist_ok=True)
    
    repo_id = "Qwen/Qwen2.5-1.5B-Instruct-GGUF"
    filename = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
    
    print(f"Downloading {filename} from {repo_id}...")
    local_path = hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        local_dir=model_dir,
        local_dir_use_symlinks=False
    )
    print(f"Model successfully downloaded to: {local_path}")

if __name__ == "__main__":
    download_model()
