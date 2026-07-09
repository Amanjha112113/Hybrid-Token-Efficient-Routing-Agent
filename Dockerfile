# --- Hybrid Token-Efficient Routing Agent ---
# Container reads /input/tasks.json, writes /output/results.json, exits.

FROM python:3.11-slim

# Keep image lean and deterministic
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    g++ gcc make cmake && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY src/ ./src/
COPY config/ ./config/
COPY models/ ./models/

# Directories the harness will mount/populate at runtime.
# Creating them here is harmless; the harness controls actual content.
RUN mkdir -p /input /output

# No port exposed, no server. Single batch run.
ENTRYPOINT ["python", "main.py"]
