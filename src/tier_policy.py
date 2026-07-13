"""
tier_policy.py

Resolves, at runtime, which Fireworks model to try for a given category
and escalation step. Model IDs are NEVER hardcoded — they are read from
the ALLOWED_MODELS environment variable and ordered cheapest-to-most-
expensive using naming heuristics (parameter-count hints, common size
adjectives). This ordering is a best-effort heuristic; if it cannot infer
sizes at all, it falls back to treating the published ALLOWED_MODELS order
as already cheapest-first, which is a common publishing convention.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import yaml

logger = logging.getLogger(__name__)

_SIZE_RE = re.compile(r"(?:(\d+)\s*x\s*)?(\d+(?:\.\d+)?)\s*b(?:illion)?\b", re.IGNORECASE)

_SMALL_HINTS = ("mini", "nano", "small", "lite")
_LARGE_HINTS = ("pro", "ultra", "large", "max", "x", "xxl", "heavy")

# Models known to be unreliable and/or unable to suppress internal
# reasoning via system prompt (dedicated "thinking" models whose visible
# content IS the reasoning trace, not narration they can be told to skip).
# Excluded from routing even if present in ALLOWED_MODELS — being allowed
# to use a model does not require using it.
_BLOCKED_MODEL_SUBSTRINGS = ("kimi-k2p5", "kimi-k2p6")


@dataclass(frozen=True)
class CategoryPolicy:
    start_tier: int
    max_escalations: int


class TierPolicy:
    def __init__(self, allowed_models: List[str], config_path: str = "config/tier_mapping.yaml"):
        if not allowed_models:
            raise ValueError("ALLOWED_MODELS is empty — cannot build a tier policy")

        self.ordered_models: List[str] = _order_models_by_estimated_cost(allowed_models)
        self._config = _load_config(config_path)
        logger.info("Model tiers resolved (cheapest -> most expensive): %s", self.ordered_models)

    def sequence_for_category(self, category: str) -> List[str]:
        """
        Return the ordered list of models to attempt for this category,
        starting at the category's configured start tier and proceeding
        upward through more expensive tiers, capped by max_escalations.
        """
        policy = self._policy_for(category)
        start = min(policy.start_tier, len(self.ordered_models) - 1)
        end = min(start + policy.max_escalations, len(self.ordered_models) - 1)
        return self.ordered_models[start : end + 1]

    def _policy_for(self, category: str) -> CategoryPolicy:
        categories_cfg: Dict = self._config.get("categories", {})
        default_cfg: Dict = self._config.get("default", {"start_tier": 0, "max_escalations": 1})
        cfg = categories_cfg.get(category, default_cfg)
        return CategoryPolicy(
            start_tier=int(cfg.get("start_tier", 0)),
            max_escalations=int(cfg.get("max_escalations", 1)),
        )

    def generation_params(self, category: str = None) -> Dict:
        """
        Return max_tokens/temperature for a call. If `category` is given
        and has its own `max_tokens` in tier_mapping.yaml, that value wins;
        otherwise falls back to the global `generation.max_tokens`.
        """
        gen_cfg = self._config.get("generation", {})
        default_max_tokens = int(gen_cfg.get("max_tokens", 500))
        temperature = float(gen_cfg.get("temperature", 0.2))

        if category is not None:
            categories_cfg: Dict = self._config.get("categories", {})
            cat_cfg = categories_cfg.get(category, {})
            max_tokens = int(cat_cfg.get("max_tokens", default_max_tokens))
        else:
            max_tokens = default_max_tokens

        return {"max_tokens": max_tokens, "temperature": temperature}


def _order_models_by_estimated_cost(models: List[str]) -> List[str]:
    """
    Best-effort ordering of model IDs from cheapest to most expensive,
    using parameter-count hints in the model name (e.g. "8b", "70b") and
    common size adjectives. Models with no discernible size hint are
    placed in the middle, preserving their relative published order.
    """
    usable = [
        m for m in models
        if not any(blocked in m.lower() for blocked in _BLOCKED_MODEL_SUBSTRINGS)
    ]
    if not usable:
        # Safety net: if blocking would leave zero models, don't block —
        # better a slow/verbose answer than a hard crash from an empty list.
        logger.warning("All models were blocked — falling back to full ALLOWED_MODELS list.")
        usable = models

    scored: List[tuple] = []
    for idx, model_id in enumerate(usable):
        score = _estimate_size_score(model_id)
        scored.append((score, idx, model_id))

    # Sort by estimated size ascending; ties broken by original published order.
    scored.sort(key=lambda t: (t[0], t[1]))
    return [model_id for _, _, model_id in scored]


def _estimate_size_score(model_id: str) -> float:
    lowered = model_id.lower()

    match = _SIZE_RE.search(lowered)
    if match:
        try:
            multiplier = float(match.group(1)) if match.group(1) else 1.0
            base = float(match.group(2))
            return multiplier * base
        except ValueError:
            pass

    if any(hint in lowered for hint in _SMALL_HINTS):
        return 1.0
    if any(hint in lowered for hint in _LARGE_HINTS):
        return 200.0

    # Unknown size: assume premium/expensive so it sorts to the top tier.
    # This prevents accidentally using a costly model as mid-tier.
    return 1000.0


def _load_config(config_path: str) -> Dict:
    path = Path(config_path)
    if not path.exists():
        logger.warning("Tier config not found at %s — using built-in defaults", config_path)
        return {"categories": {}, "default": {"start_tier": 0, "max_escalations": 1}}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}
