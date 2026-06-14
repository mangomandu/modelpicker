"""fablite — model routing harness (v1: router-only).

A cheap router model judges a task's difficulty/confidence; deterministic policy
then picks the execution-model tier and emits a validated RoutingDecision JSON.
"""
from .config import RouterConfig, load_config
from .models import (
    Alternative,
    CodeContext,
    ExecModel,
    GoldenCase,
    MetricsReport,
    Mode,
    RouterJudgment,
    RoutingDecision,
    RoutingRequest,
    TaskType,
)
from .router import route

__all__ = [
    "Mode",
    "TaskType",
    "ExecModel",
    "CodeContext",
    "RoutingRequest",
    "RouterJudgment",
    "Alternative",
    "RoutingDecision",
    "GoldenCase",
    "MetricsReport",
    "RouterConfig",
    "load_config",
    "route",
]
__version__ = "0.1.0"
