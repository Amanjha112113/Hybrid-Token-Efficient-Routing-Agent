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

_SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*b(?:illion)?\b", re.IGNORECASE)

_SMALL_HINTS = ("small", "mini", "lite", "tiny")
_LARGE_HINTS = ("large", "xl", "70b", "72b", "405b", "maverick", "scout")


@dataclass(frozen=True)
class CategoryPolicy:
    start_tier: int
    max_escalations: int


class TierPolicy:
    def __init__(self, allowed_models: List[str], config_path: str = "config/tier_mapping.yaml", local_model_id: str | None = None):
        if not allowed_models:
            raise ValueError("ALLOWED_MODELS is empty — cannot build a tier policy")

        self.ordered_models: List[str] = _order_models_by_estimated_cost(allowed_models)
        if local_model_id:
            self.ordered_models.insert(0, f"local:{local_model_id}")
            
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

    def generation_params(self) -> Dict:
        gen_cfg = self._config.get("generation", {})
        return {
            "max_tokens": int(gen_cfg.get("max_tokens", 600)),
            "temperature": float(gen_cfg.get("temperature", 0.2)),
        }


def _order_models_by_estimated_cost(models: List[str]) -> List[str]:
    """
    Best-effort ordering of model IDs from cheapest to most expensive,
    using parameter-count hints in the model name (e.g. "8b", "70b") and
    common size adjectives. Models with no discernible size hint are
    placed in the middle, preserving their relative published order.
    """
    scored: List[tuple] = []
    for idx, model_id in enumerate(models):
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
            return float(match.group(1))
        except ValueError:
            pass

    if any(hint in lowered for hint in _SMALL_HINTS):
        return 1.0
    if any(hint in lowered for hint in _LARGE_HINTS):
        return 200.0

    # Unknown size: assume mid-range so it doesn't distort the two ends.
    return 50.0


def _load_config(config_path: str) -> Dict:
    path = Path(config_path)
    if not path.exists():
        logger.warning("Tier config not found at %s — using built-in defaults", config_path)
        return {"categories": {}, "default": {"start_tier": 0, "max_escalations": 1}}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}
