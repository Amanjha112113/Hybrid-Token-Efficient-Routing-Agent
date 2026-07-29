import os
import time
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from src.escalation_controller import process_task, TaskResult
from src.fireworks_client import FireworksClient
from src.tier_policy import TierPolicy
from src.category_classifier import classify_prompt
from src.local_model import answer_local
from src.task_loader import Task

app = FastAPI(title="Hybrid Token-Efficient Routing Agent API")

# Enable CORS for frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared memory/in-memory stats
stats = {
    "total_requests": 0,
    "local_count": 0,
    "remote_count": 0,
    "tokens_saved": 0,  # Estimating what Llama-v3p1-8b would cost vs local (0 tokens)
    "tokens_used": 0,
    "history": []
}

class RouteRequest(BaseModel):
    prompt: str

class RouteResponse(BaseModel):
    task_id: str
    answer: str
    category: str
    backend: str
    tokens_used: int
    succeeded_validation: bool
    elapsed_seconds: float

# Initial configuration
api_key = os.environ.get("FIREWORKS_API_KEY", "")
base_url = os.environ.get("FIREWORKS_BASE_URL", "")
allowed_models_raw = os.environ.get("ALLOWED_MODELS", "accounts/fireworks/models/llama-v3p1-8b-instruct,accounts/fireworks/models/deepseek-v4-pro")
allowed_models = [m.strip() for m in allowed_models_raw.split(",") if m.strip()]

client = FireworksClient(api_key=api_key, base_url=base_url)
tier_policy = TierPolicy(allowed_models=allowed_models, config_path="config/tier_mapping.yaml")

@app.post("/api/route")
async def route_query(req: RouteRequest):
    start_time = time.monotonic()
    
    # Classify the prompt
    category = classify_prompt(req.prompt)
    
    # Setup dynamic task
    task_id = f"web_{int(time.time())}"
    task = Task(task_id=task_id, prompt=req.prompt)
    
    # Determine fallback routing logic
    # Local-supported tasks: sentiment, NER, text summarization
    local_capable_categories = ["sentiment_classification", "named_entity_recognition", "text_summarisation"]
    backend = "local" if category in local_capable_categories else "fireworks"
    
    succeeded_validation = False
    answer = ""
    tokens_used = 0
    
    try:
        # Run process_task directly
        res: TaskResult = await process_task(
            task=task,
            client=client,
            tier_policy=tier_policy,
            deadline=start_time + 120.0 # 2 minute timeout
        )
        
        answer = res.answer
        tokens_used = res.tokens_used
        succeeded_validation = res.succeeded_validation
        
        # Adjust backend display dynamically depending on where it ended up
        if tokens_used == 0 and res.attempts <= 1 and category in local_capable_categories:
            backend = "local"
        else:
            backend = "fireworks"
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference pipeline failed: {str(e)}")
        
    elapsed = time.monotonic() - start_time
    
    # Update Stats
    stats["total_requests"] += 1
    if backend == "local":
        stats["local_count"] += 1
        # Llama 8B prompt token estimation ~ prompt length / 4 + max output tokens (avg 150)
        estimated_saved = int(len(req.prompt) / 4) + 150
        stats["tokens_saved"] += estimated_saved
    else:
        stats["remote_count"] += 1
        stats["tokens_used"] += tokens_used
        
    log_item = {
        "timestamp": time.time(),
        "prompt": req.prompt,
        "category": category,
        "backend": backend,
        "tokens_used": tokens_used,
        "succeeded_validation": succeeded_validation,
        "elapsed_seconds": round(elapsed, 2)
    }
    stats["history"].insert(0, log_item)
    if len(stats["history"]) > 20:
        stats["history"].pop()
        
    return {
        "task_id": task_id,
        "answer": answer,
        "category": category,
        "backend": backend,
        "tokens_used": tokens_used,
        "succeeded_validation": succeeded_validation,
        "elapsed_seconds": elapsed
    }

@app.get("/api/stats")
async def get_stats():
    return stats

@app.on_event("shutdown")
async def shutdown_event():
    await client.close()
