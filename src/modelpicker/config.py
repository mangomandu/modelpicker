"""RouterConfig: tunable settings with concrete defaults, ranges, and file loading.

All routing values are configurable (JSON/YAML), never hardcoded into the policy.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

# Default execution-model price rates, blended output USD per 1M tokens, used
# only for the estimated_cost heuristic. Overridable via config.
DEFAULT_PRICE_RATES: dict[str, float] = {
    "sonnet": 15.0,
    "opus": 25.0,
    "fable": 50.0,
}


class RouterConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Where the judgment comes from:
    #   "claude_cli" -> local `claude` CLI (subscription auth, no API key)
    #   "api"        -> anthropic SDK (needs ANTHROPIC_API_KEY / an auth profile)
    judge_backend: Literal["claude_cli", "api"] = "claude_cli"
    judge_timeout_seconds: int = Field(default=120, ge=1)

    router_model: str = "sonnet"
    confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    mode_a_difficulty_boundary: float = Field(default=0.5, ge=0.0, le=1.0)
    mode_b_difficulty_boundaries: tuple[float, float] = (0.4, 0.75)
    # Half-width of the symmetric band around each boundary (the "ambiguous" zone).
    difficulty_boundary_band: float = Field(default=0.1, ge=0.0, le=1.0)
    escalation_step: int = Field(default=1, ge=1)
    per_model_price_rates: dict[str, float] = Field(
        default_factory=lambda: dict(DEFAULT_PRICE_RATES)
    )

    # --- executor (v2): run the chosen model, with graceful fallback ---
    executor_backend: Literal["claude_cli", "api"] = "claude_cli"
    execute_timeout_seconds: int = Field(default=600, ge=1)
    executor_fallback: bool = True
    # Models to treat as unavailable right now (e.g. ["fable"] while Fable is closed);
    # the executor skips them and degrades to the next tier down.
    unavailable_models: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_boundaries(self) -> "RouterConfig":
        b1, b2 = self.mode_b_difficulty_boundaries
        if not (0.0 <= b1 < b2 <= 1.0):
            raise ValueError(
                "mode_b_difficulty_boundaries must satisfy 0 <= b1 < b2 <= 1"
            )
        return self


def load_config(path: str | Path | None = None) -> RouterConfig:
    """Load a RouterConfig, applying file overrides on top of defaults."""
    if path is None:
        return RouterConfig()
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    data: dict[str, Any]
    if p.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        data = yaml.safe_load(text) or {}
    if isinstance(data.get("mode_b_difficulty_boundaries"), list):
        data["mode_b_difficulty_boundaries"] = tuple(data["mode_b_difficulty_boundaries"])
    return RouterConfig(**data)
