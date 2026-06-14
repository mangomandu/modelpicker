"""Pydantic models for modelpicker's RoutingDecision and the surrounding entities.

Five entities, kept deliberately separate (a QA-driven refinement):
  - RoutingRequest   : router input signals
  - RouterConfig     : tunable settings (in config.py)
  - RoutingDecision  : THE stdout output JSON (decision/reporting fields only)
  - GoldenCase       : deterministic test fixture, with per-mode expectations
  - MetricsReport    : optional --report-json output (never to stdout)
"""
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class Mode(str, Enum):
    A = "A"  # opus vs fable
    B = "B"  # sonnet vs opus vs fable


class TaskType(str, Enum):
    code_generation = "code_generation"
    refactor = "refactor"
    debug = "debug"
    documentation = "documentation"


class ExecModel(str, Enum):
    sonnet = "sonnet"
    opus = "opus"
    fable = "fable"


class Effort(str, Enum):
    """Effort levels Claude Code / the API accept, lowest -> highest."""

    low = "low"
    medium = "medium"
    high = "high"
    xhigh = "xhigh"
    max = "max"


class CodeContext(BaseModel):
    """Repo/code context — either raw_text (plain-text file) OR structured fields."""

    model_config = ConfigDict(extra="forbid")

    raw_text: Optional[str] = None
    files: Optional[list[str]] = None
    diff: Optional[str] = None
    repo_state: Optional[str] = None
    size: Optional[int] = Field(default=None, ge=0)
    complexity: Optional[Literal["low", "medium", "high"]] = None


class RoutingRequest(BaseModel):
    """Input signals to the router."""

    model_config = ConfigDict(extra="forbid")

    mode: Mode
    prompt: str = Field(min_length=1)
    task_type: Optional[TaskType] = None
    code_context: Optional[CodeContext] = None


class RouterJudgment(BaseModel):
    """What the (mockable) router model returns about a task."""

    model_config = ConfigDict(extra="forbid")

    difficulty_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(min_length=1)
    # Whether the task warrants multi-agent orchestration (ultracode) rather than a
    # single agent — true for broad/decomposable/verification-heavy work.
    needs_ultracode: bool = False


class Alternative(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: ExecModel
    score: float = Field(ge=0.0, le=1.0)


class RoutingDecision(BaseModel):
    """THE stdout output JSON (router-only, v1).

    Contains exactly the decision/reporting fields — no request, config, or
    golden fields (enforced by extra='forbid').
    """

    model_config = ConfigDict(extra="forbid")

    selected_model: ExecModel
    # Per-turn effort for the chosen model (derived from difficulty, clamped to
    # what selected_model supports). The cheap lever — keeps the model's cache warm.
    effort: Effort
    reasoning: str = Field(min_length=1)
    difficulty_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    estimated_tokens: float = Field(ge=0.0)
    estimated_cost: float = Field(ge=0.0)
    escalated: bool
    needs_ultracode: bool = False
    alternatives: list[Alternative]
    latency: float = Field(ge=0.0)


class GoldenCase(BaseModel):
    """Deterministic test fixture with per-mode expectations.

    `routing_request` holds the input signals (prompt/task_type/code_context)
    without `mode`; mode is applied per evaluation (A and B both checked).
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    routing_request: dict
    mocked_router_response: RouterJudgment
    mode_a_expected_model: ExecModel
    mode_a_expected_escalated: bool
    mode_b_expected_model: ExecModel
    mode_b_expected_escalated: bool


class MetricsReport(BaseModel):
    """Optional --report-json output. Reporting only — never a pass/fail gate."""

    model_config = ConfigDict(extra="forbid")

    routing_accuracy: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    latency_summary: dict
    cost_summary: dict
    n_cases: int = Field(ge=0)
    generated_at: str


class ExecutionResult(BaseModel):
    """v2 executor output — the task actually run on the chosen (or fallback) model."""

    model_config = ConfigDict(extra="forbid")

    requested_model: ExecModel
    executed_model: ExecModel
    fell_back: bool
    fallback_reason: Optional[str] = None
    output: str
    latency: float = Field(ge=0.0)
