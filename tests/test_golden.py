"""Golden tests: deterministic routing decisions per mode, with a mocked router."""
from pathlib import Path

import pytest
import yaml

from fableite.config import RouterConfig
from fableite.models import GoldenCase, Mode, RouterJudgment, RoutingDecision, RoutingRequest
from fableite.router import route

FIXTURE = Path(__file__).parent / "fixtures" / "golden_cases.yaml"


def _load_cases() -> list[GoldenCase]:
    raw = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    return [GoldenCase(**c) for c in raw]


CASES = _load_cases()
DECISION_KEYS = {
    "selected_model", "reasoning", "difficulty_score", "confidence",
    "estimated_tokens", "estimated_cost", "escalated", "alternatives", "latency",
}


def _fixed(judgment: RouterJudgment):
    def judge(_request, _config):
        return judgment

    return judge


def _request(case: GoldenCase, mode: Mode) -> RoutingRequest:
    return RoutingRequest(mode=mode, **case.routing_request)


def _validate_schema(d: RoutingDecision) -> None:
    assert 0.0 <= d.difficulty_score <= 1.0
    assert 0.0 <= d.confidence <= 1.0
    assert d.estimated_tokens >= 0
    assert d.estimated_cost >= 0
    assert d.latency >= 0
    assert d.reasoning.strip()
    assert isinstance(d.alternatives, list) and len(d.alternatives) >= 1
    for alt in d.alternatives:
        assert 0.0 <= alt.score <= 1.0
    # stdout JSON carries exactly the decision fields — no request/config/golden keys.
    assert set(d.model_dump().keys()) == DECISION_KEYS


def test_suite_size_8_to_12():
    assert 8 <= len(CASES) <= 12


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_mode_a(case: GoldenCase):
    d = route(_request(case, Mode.A), RouterConfig(), judge=_fixed(case.mocked_router_response))
    assert d.selected_model.value == case.mode_a_expected_model.value
    assert d.escalated is case.mode_a_expected_escalated
    assert d.selected_model.value in {"opus", "fable"}
    _validate_schema(d)


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_mode_b(case: GoldenCase):
    d = route(_request(case, Mode.B), RouterConfig(), judge=_fixed(case.mocked_router_response))
    assert d.selected_model.value == case.mode_b_expected_model.value
    assert d.escalated is case.mode_b_expected_escalated
    assert d.selected_model.value in {"sonnet", "opus", "fable"}
    _validate_schema(d)


def test_determinism_repeated_runs_match():
    case = CASES[0]
    a = route(_request(case, Mode.B), RouterConfig(), judge=_fixed(case.mocked_router_response))
    b = route(_request(case, Mode.B), RouterConfig(), judge=_fixed(case.mocked_router_response))
    # Everything except the measured latency must be identical.
    da, db = a.model_dump(), b.model_dump()
    da.pop("latency"), db.pop("latency")
    assert da == db
