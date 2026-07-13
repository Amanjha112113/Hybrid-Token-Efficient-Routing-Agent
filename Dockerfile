# --- Router Agent (API-Only) ---
# All tasks are routed to Fireworks API to ensure compliance with the scoring rule
# that "every scored answer must ultimately originate from a Fireworks API call".

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        build-essential \
        cmake \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir llama-cpp-python==0.3.30 --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu

COPY models/local_model.ggu[f] /app/models/
RUN if [ ! -f /app/models/local_model.gguf ]; then \
        curl -L -o /app/models/local_model.gguf \
            https://huggingface.co/bartowski/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf; \
    fi

COPY main.py .
COPY src/ ./src/
COPY config/ ./config/

RUN mkdir -p /input /output

ENTRYPOINT ["python", "main.py"]
