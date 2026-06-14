"""Executor tests: fallback chain + graceful degradation. No live model is called."""
import pytest

from modelpicker.config import RouterConfig
from modelpicker.executor import ModelUnavailable, _fallback_chain, execute
from modelpicker.models import (
    Alternative,
    CodeContext,
    ExecModel,
    Mode,
    RoutingDecision,
    RoutingRequest,
)


def _decision(model: str) -> RoutingDecision:
    return RoutingDecision(
        selected_model=model, reasoning="r", difficulty_score=0.9, confidence=0.9,
        estimated_tokens=10.0, estimated_cost=0.0, escalated=False,
        alternatives=[Alternative(model="opus", score=0.5)], latency=0.0,
    )


def _req(mode: Mode = Mode.B) -> RoutingRequest:
    return RoutingRequest(mode=mode, prompt="do the thing")


def test_fallback_chain():
    cfg = RouterConfig()
    assert _fallback_chain(Mode.B, "fable", cfg) == ["fable", "opus", "sonnet"]
    assert _fallback_chain(Mode.B, "opus", cfg) == ["opus", "sonnet"]
    assert _fallback_chain(Mode.A, "fable", cfg) == ["fable", "opus"]
    # fallback disabled -> just the selected model
    assert _fallback_chain(Mode.B, "fable", RouterConfig(executor_fallback=False)) == ["fable"]


def test_runs_selected_when_available():
    seen = []

    def runner(task, model, config):
        seen.append(model)
        return f"answer from {model}"

    res = execute(_req(), _decision("fable"), RouterConfig(), runner=runner)
    assert seen == ["fable"]
    assert res.executed_model is ExecModel.fable
    assert res.fell_back is False
    assert res.fallback_reason is None
    assert res.output == "answer from fable"


def test_falls_back_when_model_listed_unavailable():
    seen = []

    def runner(task, model, config):
        seen.append(model)
        return f"answer from {model}"

    cfg = RouterConfig(unavailable_models=["fable"])
    res = execute(_req(), _decision("fable"), cfg, runner=runner)
    assert seen == ["opus"]  # fable skipped, opus ran
    assert res.requested_model is ExecModel.fable
    assert res.executed_model is ExecModel.opus
    assert res.fell_back is True
    assert "fable" in (res.fallback_reason or "")


def test_falls_back_on_runner_error():
    def runner(task, model, config):
        if model == "fable":
            raise ModelUnavailable("fable: closed")
        return f"answer from {model}"

    res = execute(_req(), _decision("fable"), RouterConfig(), runner=runner)
    assert res.executed_model is ExecModel.opus
    assert res.fell_back is True
    assert "fable" in (res.fallback_reason or "")


def test_no_fallback_when_disabled():
    def runner(task, model, config):
        raise ModelUnavailable("fable: closed")

    cfg = RouterConfig(executor_fallback=False)
    with pytest.raises(RuntimeError):
        execute(_req(), _decision("fable"), cfg, runner=runner)


def test_chain_exhausted_raises():
    def runner(task, model, config):
        raise ModelUnavailable(f"{model}: down")

    with pytest.raises(RuntimeError, match="No available model"):
        execute(_req(), _decision("fable"), RouterConfig(), runner=runner)


def test_task_prompt_includes_context():
    captured = {}

    def runner(task, model, config):
        captured["task"] = task
        return "ok"

    req = RoutingRequest(mode=Mode.B, prompt="fix the bug",
                         code_context=CodeContext(raw_text="def f(): pass"))
    execute(req, _decision("sonnet"), RouterConfig(), runner=runner)
    assert "fix the bug" in captured["task"] and "def f()" in captured["task"]
