"""Core routing policy.

Deterministic given a RouterJudgment (difficulty/confidence). The judgment comes
from a router model (default Sonnet) in production, or a fixture in golden tests.

Policy:
  1. difficulty_score -> base tier via the per-mode config boundaries.
  2. Escalation trigger = difficulty within the boundary band  OR  confidence
     below confidence_threshold (performance-first bias).
  3. On trigger, move the selection up by escalation_step tiers (clamped to the
     mode's top tier). escalated = the selection actually moved up.
"""
from __future__ import annotations

import time
from typing import Callable, Optional

from .config import RouterConfig
from .constants import TIER_ORDER
from .models import (
    Alternative,
    ExecModel,
    Mode,
    RouterJudgment,
    RoutingDecision,
    RoutingRequest,
)

Judge = Callable[[RoutingRequest, RouterConfig], RouterJudgment]


def _boundaries(mode: Mode, config: RouterConfig) -> list[float]:
    if mode is Mode.A:
        return [config.mode_a_difficulty_boundary]
    return list(config.mode_b_difficulty_boundaries)


def _base_tier_index(mode: Mode, difficulty: float, config: RouterConfig) -> int:
    """Tier index = number of boundaries the difficulty is at or above."""
    return sum(1 for b in _boundaries(mode, config) if difficulty >= b)


def _within_band(difficulty: float, mode: Mode, config: RouterConfig) -> bool:
    band = config.difficulty_boundary_band
    return any(abs(difficulty - b) <= band for b in _boundaries(mode, config))


def _tier_center(mode: Mode, index: int, config: RouterConfig) -> float:
    """Midpoint of the difficulty interval mapping to tier `index`."""
    edges = [0.0] + _boundaries(mode, config) + [1.0]
    return (edges[index] + edges[index + 1]) / 2.0


def _estimate_tokens(request: RoutingRequest) -> float:
    """Rough heuristic from prompt + code_context size (~4 chars/token + output allowance)."""
    chars = len(request.prompt)
    cc = request.code_context
    if cc is not None:
        if cc.raw_text:
            chars += len(cc.raw_text)
        if cc.diff:
            chars += len(cc.diff)
        if cc.files:
            chars += sum(len(f) for f in cc.files)
        if cc.size:
            chars += int(cc.size)
    return round(chars / 4.0 + 500.0, 2)


def _default_judge(request: RoutingRequest, config: RouterConfig) -> RouterJudgment:
    # Lazy import so offline/test use never needs the anthropic package or a key.
    from .llm import default_judge

    return default_judge(request, config)


def route(
    request: RoutingRequest,
    config: Optional[RouterConfig] = None,
    judge: Optional[Judge] = None,
) -> RoutingDecision:
    config = config or RouterConfig()
    judge = judge or _default_judge

    t0 = time.perf_counter()
    judgment = judge(request, config)
    latency = time.perf_counter() - t0

    tiers = TIER_ORDER[request.mode.value]
    base = _base_tier_index(request.mode, judgment.difficulty_score, config)

    trigger = (
        _within_band(judgment.difficulty_score, request.mode, config)
        or judgment.confidence < config.confidence_threshold
    )
    selected_idx = (
        min(base + config.escalation_step, len(tiers) - 1) if trigger else base
    )
    escalated = selected_idx > base
    selected_model = ExecModel(tiers[selected_idx])

    estimated_tokens = _estimate_tokens(request)
    rate = config.per_model_price_rates.get(selected_model.value, 0.0)
    estimated_cost = round(estimated_tokens / 1_000_000.0 * rate, 6)

    alternatives: list[Alternative] = []
    for i, name in enumerate(tiers):
        if i == selected_idx:
            continue
        dist = abs(judgment.difficulty_score - _tier_center(request.mode, i, config))
        alternatives.append(
            Alternative(model=ExecModel(name), score=round(max(0.0, 1.0 - dist), 4))
        )

    return RoutingDecision(
        selected_model=selected_model,
        reasoning=judgment.reasoning,
        difficulty_score=judgment.difficulty_score,
        confidence=judgment.confidence,
        estimated_tokens=estimated_tokens,
        estimated_cost=estimated_cost,
        escalated=escalated,
        alternatives=alternatives,
        latency=round(latency, 6),
    )
