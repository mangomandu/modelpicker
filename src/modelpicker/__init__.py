"""modelpicker — model routing harness.

v1 (router): a cheap router model judges a task's difficulty/confidence; a
deterministic policy picks the execution-model tier and emits a RoutingDecision.
v2 (executor): runs the task on the chosen model, degrading gracefully when a
model is unavailable.
"""
from .config import RouterConfig, load_config
from .executor import ModelUnavailable, execute
from .models import (
    Alternative,
    CodeContext,
    ExecModel,
    ExecutionResult,
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
    "ExecutionResult",
    "RouterConfig",
    "load_config",
    "route",
    "execute",
    "ModelUnavailable",
]
__version__ = "0.2.0"
