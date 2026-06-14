"""Judgment backends: JSON parsing + backend dispatch. No real model is called."""
import subprocess
import types

import pytest

import fablite.llm as llm
from fablite.config import RouterConfig
from fablite.models import Mode, RouterJudgment, RoutingRequest


def _req() -> RoutingRequest:
    return RoutingRequest(mode=Mode.A, prompt="do a thing")


def test_parse_clean_json():
    j = llm._parse_judgment('{"difficulty_score": 0.4, "confidence": 0.9, "reasoning": "ok"}')
    assert (j.difficulty_score, j.confidence, j.reasoning) == (0.4, 0.9, "ok")


def test_parse_tolerates_fence_and_prose():
    text = 'Sure!\n```json\n{"difficulty_score": 0.7, "confidence": 0.8, "reasoning": "x"}\n```'
    assert llm._parse_judgment(text).difficulty_score == 0.7


def test_parse_clamps_out_of_range():
    j = llm._parse_judgment('{"difficulty_score": 1.4, "confidence": -0.2, "reasoning": "x"}')
    assert j.difficulty_score == 1.0 and j.confidence == 0.0


def test_parse_non_json_raises():
    with pytest.raises(RuntimeError):
        llm._parse_judgment("no json here")


def test_dispatch_uses_api_backend(monkeypatch):
    seen = []

    def fake_api(r, c):
        seen.append("api")
        return RouterJudgment(difficulty_score=0.1, confidence=0.9, reasoning="a")

    def fail_cli(r, c):
        pytest.fail("cli_judge should not run for judge_backend='api'")

    monkeypatch.setattr(llm, "api_judge", fake_api)
    monkeypatch.setattr(llm, "cli_judge", fail_cli)
    out = llm.judge(_req(), RouterConfig(judge_backend="api"))
    assert seen == ["api"] and out.reasoning == "a"


def test_dispatch_uses_cli_backend(monkeypatch):
    seen = []

    def fake_cli(r, c):
        seen.append("cli")
        return RouterJudgment(difficulty_score=0.1, confidence=0.9, reasoning="c")

    def fail_api(r, c):
        pytest.fail("api_judge should not run for judge_backend='claude_cli'")

    monkeypatch.setattr(llm, "cli_judge", fake_cli)
    monkeypatch.setattr(llm, "api_judge", fail_api)
    out = llm.judge(_req(), RouterConfig(judge_backend="claude_cli"))
    assert seen == ["cli"] and out.reasoning == "c"


def test_cli_judge_parses_subprocess_output(monkeypatch):
    def fake_run(cmd, **kwargs):
        assert cmd[0] == "claude" and "-p" in cmd and "--model" in cmd
        return types.SimpleNamespace(
            returncode=0,
            stdout='{"difficulty_score": 0.6, "confidence": 0.7, "reasoning": "mid"}',
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    j = llm.cli_judge(_req(), RouterConfig())
    assert j.difficulty_score == 0.6 and j.reasoning == "mid"


def test_cli_judge_missing_binary_raises(monkeypatch):
    def boom(cmd, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", boom)
    with pytest.raises(RuntimeError, match="not found"):
        llm.cli_judge(_req(), RouterConfig())


def test_cli_judge_nonzero_exit_raises(monkeypatch):
    def fake_run(cmd, **kwargs):
        return types.SimpleNamespace(returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="failed"):
        llm.cli_judge(_req(), RouterConfig())
