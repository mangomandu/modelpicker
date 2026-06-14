"""Unit tests for the routing policy primitives and escalation behavior."""
from modelpicker.config import RouterConfig
from modelpicker.models import Effort, ExecModel, Mode, RouterJudgment, RoutingRequest
from modelpicker.router import (
    _base_tier_index,
    _clamp_effort,
    _ideal_effort,
    _within_band,
    route,
)


def _j(d: float, c: float, r: str = "reasoning"):
    return RouterJudgment(difficulty_score=d, confidence=c, reasoning=r)


def _req(mode: Mode, prompt: str = "do a thing"):
    return RoutingRequest(mode=mode, prompt=prompt)


def test_needs_ultracode_propagates_from_judgment():
    yes = lambda r, c: RouterJudgment(
        difficulty_score=0.8, confidence=0.9, reasoning="broad audit", needs_ultracode=True)
    no = lambda r, c: RouterJudgment(
        difficulty_score=0.8, confidence=0.9, reasoning="single fix", needs_ultracode=False)
    assert route(_req(Mode.B), RouterConfig(), judge=yes).needs_ultracode is True
    assert route(_req(Mode.B), RouterConfig(), judge=no).needs_ultracode is False


def test_base_tier_mode_a():
    cfg = RouterConfig()
    assert _base_tier_index(Mode.A, 0.2, cfg) == 0
    assert _base_tier_index(Mode.A, 0.5, cfg) == 1
    assert _base_tier_index(Mode.A, 0.99, cfg) == 1


def test_base_tier_mode_b():
    cfg = RouterConfig()
    assert _base_tier_index(Mode.B, 0.1, cfg) == 0
    assert _base_tier_index(Mode.B, 0.5, cfg) == 1
    assert _base_tier_index(Mode.B, 0.9, cfg) == 2


def test_within_band():
    cfg = RouterConfig()
    assert _within_band(0.55, Mode.A, cfg) is True   # |0.55-0.5| <= 0.1
    assert _within_band(0.20, Mode.A, cfg) is False


def test_low_confidence_escalates():
    d = route(_req(Mode.B), RouterConfig(), judge=lambda r, c: _j(0.10, 0.30))
    assert d.selected_model is ExecModel.opus  # base sonnet, low conf -> +1
    assert d.escalated is True


def test_clamp_at_top_sets_escalated_false():
    # In the top band but already at the top tier -> triggered but no movement.
    d = route(_req(Mode.B), RouterConfig(), judge=lambda r, c: _j(0.82, 0.90))
    assert d.selected_model is ExecModel.fable
    assert d.escalated is False


def test_escalation_step_configurable():
    cfg = RouterConfig(escalation_step=2)
    d = route(_req(Mode.B), cfg, judge=lambda r, c: _j(0.10, 0.30))  # sonnet + low conf
    assert d.selected_model is ExecModel.fable  # jumped two tiers
    assert d.escalated is True


def test_config_boundary_changes_behavior():
    high_boundary = route(
        _req(Mode.A), RouterConfig(mode_a_difficulty_boundary=0.9),
        judge=lambda r, c: _j(0.6, 0.95),
    )
    low_boundary = route(
        _req(Mode.A), RouterConfig(mode_a_difficulty_boundary=0.3),
        judge=lambda r, c: _j(0.6, 0.95),
    )
    assert high_boundary.selected_model is ExecModel.opus   # 0.6 < 0.9 -> opus
    assert low_boundary.selected_model is ExecModel.fable   # 0.6 >= 0.3 -> fable


def test_input_signals_affect_decision():
    judge = lambda r, c: _j(0.9, 0.95)
    small = route(RoutingRequest(mode=Mode.A, prompt="x"), RouterConfig(), judge=judge)
    big = route(RoutingRequest(mode=Mode.A, prompt="x" * 4000), RouterConfig(), judge=judge)
    assert big.estimated_tokens > small.estimated_tokens


def test_alternatives_exclude_selected():
    d = route(_req(Mode.B), RouterConfig(), judge=lambda r, c: _j(0.1, 0.95))
    models = {a.model for a in d.alternatives}
    assert d.selected_model not in models
    assert len(d.alternatives) == 2  # the other two tiers in Mode B


# --- effort routing (the cheap lever) ---

def test_ideal_effort_scales_with_difficulty():
    cfg = RouterConfig()  # cut points (0.2, 0.4, 0.65, 0.85)
    assert _ideal_effort(0.10, cfg) == "low"
    assert _ideal_effort(0.30, cfg) == "medium"
    assert _ideal_effort(0.50, cfg) == "high"
    assert _ideal_effort(0.70, cfg) == "xhigh"
    assert _ideal_effort(0.90, cfg) == "max"


def test_clamp_effort_respects_model_support():
    # Sonnet has no xhigh -> clamps down to the highest supported at or below it.
    assert _clamp_effort("xhigh", "sonnet") == "high"
    assert _clamp_effort("max", "sonnet") == "max"      # sonnet does support max
    assert _clamp_effort("xhigh", "opus") == "xhigh"    # opus supports xhigh
    assert _clamp_effort("low", "fable") == "low"


def test_route_sets_effort_from_difficulty():
    # Mode A: trivial -> opus + low ; frontier -> fable + max (both support full set).
    easy = route(_req(Mode.A), RouterConfig(), judge=lambda r, c: _j(0.10, 0.95))
    assert easy.selected_model is ExecModel.opus and easy.effort is Effort.low
    hard = route(_req(Mode.A), RouterConfig(), judge=lambda r, c: _j(0.90, 0.95))
    assert hard.selected_model is ExecModel.fable and hard.effort is Effort.max


def test_ultracode_raises_effort_to_at_least_xhigh():
    # A trivial-scored but ultracode task should still get >= xhigh effort.
    j = lambda r, c: RouterJudgment(
        difficulty_score=0.10, confidence=0.95, reasoning="broad audit", needs_ultracode=True)
    # Mode A -> opus supports xhigh, so effort lands on xhigh.
    d = route(_req(Mode.A), RouterConfig(), judge=j)
    assert d.effort is Effort.xhigh
    # On sonnet (Mode B, trivial) xhigh clamps down to high.
    d2 = route(_req(Mode.B), RouterConfig(), judge=j)
    assert d2.selected_model is ExecModel.sonnet and d2.effort is Effort.high
