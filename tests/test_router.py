"""Unit tests for the routing policy primitives and escalation behavior."""
from modelpicker.config import RouterConfig
from modelpicker.models import ExecModel, Mode, RouterJudgment, RoutingRequest
from modelpicker.router import _base_tier_index, _within_band, route


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
