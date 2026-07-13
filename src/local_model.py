import os
import logging
import asyncio
import functools
import threading
import queue
from typing import Optional

logger = logging.getLogger(__name__)

# Robust model path resolution: check workspace local models folder first,
# then environment variable, then fallback.
_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_local_workspace_path = os.path.join(_base_dir, "models", "local_model.gguf")

if os.path.exists(_local_workspace_path):
    MODEL_PATH = _local_workspace_path
else:
    MODEL_PATH = os.environ.get("LOCAL_MODEL_PATH", "/app/models/local_model.gguf")

_llm = None
_local_sem = None
_local_queue = None
_local_thread = None

def _local_worker(q):
    while True:
        item = q.get()
        if item is None:
            break
        func, loop, fut = item
        try:
            res = func()
            if not fut.cancelled():
                loop.call_soon_threadsafe(fut.set_result, res)
        except Exception as e:
            if not fut.cancelled():
                loop.call_soon_threadsafe(fut.set_exception, e)
        finally:
            q.task_done()

def _enqueue_local_task(func):
    global _local_queue, _local_thread
    if _local_queue is None:
        _local_queue = queue.Queue()
    if _local_thread is None or not _local_thread.is_alive():
        _local_thread = threading.Thread(
            target=_local_worker,
            args=(_local_queue,),
            name="local_llm",
            daemon=True
        )
        _local_thread.start()
        
    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    _local_queue.put((func, loop, fut))
    return fut

def _get_local_sem():
    global _local_sem
    if _local_sem is None:
        _local_sem = asyncio.Semaphore(1)
    return _local_sem

def _get_llm():
    global _llm
    if _llm is None:
        try:
            from llama_cpp import Llama
            logger.info(f"Loading local model from {MODEL_PATH} ...")
            
            # Use small n_ctx to prevent OOM.
            _llm = Llama(
                model_path=MODEL_PATH,
                n_ctx=int(os.environ.get("LOCAL_LLM_N_CTX", "2048")),
                n_threads=min(os.cpu_count() or 2, 4),
                verbose=False,
            )
            logger.info("Local model loaded successfully.")
        except ImportError:
            logger.error("llama_cpp not installed, local model unavailable.")
        except Exception as e:
            logger.error(f"Failed to load local model: {e}")
            
    return _llm

SYSTEM_PROMPTS = {
    "factual_knowledge": "Answer concisely in one sentence or phrase. No commentary.",
    "sentiment_classification": (
        "Output ONLY the exact sentiment label: 'Positive', 'Negative', or 'Neutral'. "
        "Do not add any justification, explanation, or other text.\n\n"
        "Example:\n"
        "Review: 'Oh, fantastic! The package arrived three weeks late and the item inside was shattered. I absolutely love paying for broken garbage.'\n"
        "Output: Negative"
    ),
    "text_summarisation": (
        "Summarize the text in exactly one sentence. Do not add any introductory text, commentary, or explanation.\n\n"
        "Example:\n"
        "Text: 'The human brain contains roughly 86 billion neurons. These neurons communicate through trillions of synaptic connections. Functional MRI has shown that these pathways remain plastic even into adulthood.'\n"
        "Output: The human brain's 86 billion neurons communicate via trillions of synaptic connections that remain plastic into adulthood."
    ),
    "named_entity_recognition": (
        "Extract all named entities. For each entity, output exactly one line in the format: '- [entity name]: [type]' "
        "where type is one of: Person, Organization, Location, Date, Product, Event. Output ONLY the list. No explanations.\n\n"
        "Example:\n"
        "Text: 'Google was founded by Larry Page in September 1998 in California.'\n"
        "Output:\n"
        "- Google: Organization\n"
        "- Larry Page: Person\n"
        "- September 1998: Date\n"
        "- California: Location"
    ),
}

async def answer_local(prompt: str, category: str) -> Optional[str]:
    """
    Generate an answer using the local LLM.
    Returns None if the local LLM is unavailable or fails.
    """
    sem = _get_local_sem()
    
    async with sem:
        # Load the model weights inside the background thread so it doesn't freeze the event loop
        llm = await asyncio.to_thread(_get_llm)
        if llm is None:
            return None
            
        system = SYSTEM_PROMPTS.get(category, SYSTEM_PROMPTS["factual_knowledge"])
        
        # Optimize generation length to prevent wasting CPU cycles on constrained runners
        if category == "sentiment_classification":
            max_tokens = 10
        elif category == "text_summarisation":
            max_tokens = 100
        elif category == "named_entity_recognition":
            max_tokens = 120
        else:
            max_tokens = 100

        try:
            func = functools.partial(
                llm.create_chat_completion,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=max_tokens,
            )
            
            # Enqueue and await with a timeout of 20 seconds
            out = await asyncio.wait_for(_enqueue_local_task(func), timeout=20.0)
            text = out["choices"][0]["message"]["content"].strip()
            total_tokens = out.get("usage", {}).get("total_tokens", 0)
            logger.debug(f"Local model answered. Used {total_tokens} local tokens.")
            return text
        except asyncio.TimeoutError:
            logger.warning("Local model inference timed out (exceeded 20s), falling back to API.")
            return None
        except Exception as e:
            logger.warning(f"Local model generation failed: {e}")
            return None
