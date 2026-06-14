"""CLI tests — run in-process with the router judge patched (no live API)."""
import json

import pytest

import modelpicker.executor as executor_mod
import modelpicker.router as router_mod
from modelpicker.cli import main
from modelpicker.models import RouterJudgment

DECISION_KEYS = {
    "selected_model", "effort", "reasoning", "difficulty_score", "confidence",
    "estimated_tokens", "estimated_cost", "escalated", "needs_ultracode",
    "alternatives", "latency",
}


@pytest.fixture
def hard_task(monkeypatch):
    def fake(_request, _config):
        return RouterJudgment(difficulty_score=0.9, confidence=0.95, reasoning="hard task")

    monkeypatch.setattr(router_mod, "_default_judge", fake)


def test_cli_outputs_only_decision_json(hard_task, capsys):
    rc = main(["route", "--mode", "A", "--prompt", "design a distributed system"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["selected_model"] == "fable"  # difficulty 0.9 -> fable in Mode A
    assert set(data.keys()) == DECISION_KEYS


def test_cli_report_json_is_written_and_unlabeled(hard_task, capsys, tmp_path):
    report_path = tmp_path / "report.json"
    rc = main(["route", "--mode", "B", "--prompt", "x", "--report-json", str(report_path)])
    assert rc == 0
    # stdout still holds only the decision.
    assert set(json.loads(capsys.readouterr().out).keys()) == DECISION_KEYS
    report = json.loads(report_path.read_text())
    assert report["routing_accuracy"] is None  # unlabeled single CLI run
    assert report["n_cases"] == 1
    assert "latency_summary" in report and "cost_summary" in report


def test_cli_task_type_mode_b(hard_task, capsys):
    rc = main(["route", "--mode", "B", "--prompt", "fix bug", "--task-type", "debug"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["selected_model"] in {"sonnet", "opus", "fable"}


def test_cli_context_file_raw_text(hard_task, capsys, tmp_path):
    ctx = tmp_path / "ctx.txt"
    ctx.write_text("some repo context here", encoding="utf-8")
    rc = main(["route", "--mode", "A", "--prompt", "x", "--context-file", str(ctx)])
    assert rc == 0
    # larger context => larger token estimate than an empty-context run.
    with_ctx = json.loads(capsys.readouterr().out)["estimated_tokens"]
    main(["route", "--mode", "A", "--prompt", "x"])
    without_ctx = json.loads(capsys.readouterr().out)["estimated_tokens"]
    assert with_ctx > without_ctx


# --- v2: `run` (route + execute) ---

@pytest.fixture
def fake_runner(monkeypatch):
    monkeypatch.setattr(executor_mod, "run_model",
                        lambda task, model, config: f"<<output from {model}>>")


def test_cli_run_executes_and_prints_output(hard_task, fake_runner, capsys):
    rc = main(["run", "--mode", "A", "--prompt", "design a distributed system"])
    assert rc == 0
    out = capsys.readouterr()
    assert "<<output from fable>>" in out.out   # hard -> fable, ran fable
    assert "routed→fable" in out.err
    assert "ran→fable" in out.err


def test_cli_run_falls_back_when_unavailable(hard_task, fake_runner, capsys):
    rc = main(["run", "--mode", "B", "--prompt", "design a distributed system",
               "--unavailable", "fable"])
    assert rc == 0
    out = capsys.readouterr()
    assert "<<output from opus>>" in out.out    # fable closed -> opus
    assert "fell back" in out.err


def test_cli_run_json(hard_task, fake_runner, capsys):
    rc = main(["run", "--mode", "A", "--prompt", "x", "--json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["decision"]["selected_model"] == "fable"
    assert data["execution"]["executed_model"] == "fable"
    assert data["execution"]["output"] == "<<output from fable>>"
