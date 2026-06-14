"""Pydantic schema validation: enums, ranges, and the no-extra-fields guarantee."""
import pytest
from pydantic import ValidationError

from fableite.models import (
    Alternative,
    CodeContext,
    ExecModel,
    Mode,
    RoutingDecision,
    RoutingRequest,
    TaskType,
)


def _decision_kwargs(**over):
    base = dict(
        selected_model="opus",
        reasoning="because",
        difficulty_score=0.5,
        confidence=0.8,
        estimated_tokens=10.0,
        estimated_cost=0.001,
        escalated=False,
        alternatives=[Alternative(model="fable", score=0.5)],
        latency=0.01,
    )
    base.update(over)
    return base


def test_routing_request_coerces_enums():
    r = RoutingRequest(mode="A", prompt="x", task_type="debug")
    assert r.mode is Mode.A
    assert r.task_type is TaskType.debug


def test_valid_decision():
    d = RoutingDecision(**_decision_kwargs())
    assert d.selected_model is ExecModel.opus


def test_score_out_of_range_rejected():
    with pytest.raises(ValidationError):
        Alternative(model="opus", score=1.5)


def test_difficulty_out_of_range_rejected():
    with pytest.raises(ValidationError):
        RoutingDecision(**_decision_kwargs(difficulty_score=2.0))


def test_negative_cost_rejected():
    with pytest.raises(ValidationError):
        RoutingDecision(**_decision_kwargs(estimated_cost=-1.0))


def test_decision_rejects_request_fields():
    # 'mode' is a request field, not a decision field -> extra='forbid' rejects it.
    with pytest.raises(ValidationError):
        RoutingDecision(mode="A", **_decision_kwargs())


def test_code_context_raw_text_only():
    c = CodeContext(raw_text="hello world")
    assert c.raw_text == "hello world"
    assert c.files is None


def test_invalid_task_type_rejected():
    with pytest.raises(ValidationError):
        RoutingRequest(mode="A", prompt="x", task_type="not_a_type")
