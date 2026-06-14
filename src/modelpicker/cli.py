"""modelpicker CLI.

  modelpicker route ...   -> print a RoutingDecision JSON (v1, router-only)
  modelpicker run   ...   -> route, then run the task on the chosen model with
                             graceful fallback (v2 executor)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

import yaml

from .config import load_config
from .executor import execute
from .models import CodeContext, Mode, RoutingRequest, TaskType
from .report import build_report
from .router import route


def _load_context_file(path: Optional[str]) -> Optional[CodeContext]:
    """A plain-text file -> code_context.raw_text; a JSON/YAML mapping -> structured fields."""
    if not path:
        return None
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() in (".json", ".yaml", ".yml"):
        data = json.loads(text) if p.suffix.lower() == ".json" else yaml.safe_load(text)
        if isinstance(data, dict):
            return CodeContext(**data)
    return CodeContext(raw_text=text)


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--mode", required=True, choices=["A", "B"],
                   help="A = Opus/Fable, B = Sonnet/Opus/Fable")
    p.add_argument("--prompt", required=True, help="Task description")
    p.add_argument("--task-type", choices=[t.value for t in TaskType], default=None)
    p.add_argument("--context-file", default=None,
                   help="Path to code context (plain text, or JSON/YAML)")
    p.add_argument("--config", default=None, help="Path to a config (JSON/YAML)")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="modelpicker", description="Model routing harness.")
    sub = parser.add_subparsers(dest="command", required=True)

    r = sub.add_parser("route", help="Route a task and print a RoutingDecision JSON.")
    _add_common(r)
    r.add_argument("--report-json", default=None,
                   help="Write a metrics report (stdout stays decision-only)")

    e = sub.add_parser("run", help="Route, then run the task on the chosen model (with fallback).")
    _add_common(e)
    e.add_argument("--unavailable", default=None,
                   help="Comma-separated models to treat as unavailable now (e.g. 'fable')")
    e.add_argument("--json", action="store_true", help="Print decision + execution as JSON")
    return parser


def _build_request(args: argparse.Namespace) -> RoutingRequest:
    return RoutingRequest(
        mode=Mode(args.mode),
        prompt=args.prompt,
        task_type=TaskType(args.task_type) if args.task_type else None,
        code_context=_load_context_file(args.context_file),
    )


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    config = load_config(args.config)
    request = _build_request(args)

    if args.command == "route":
        decision = route(request, config)
        sys.stdout.write(decision.model_dump_json(indent=2) + "\n")
        if args.report_json:
            # Unlabeled single CLI run -> routing_accuracy is null.
            report = build_report([decision], routing_accuracy=None)
            Path(args.report_json).write_text(
                report.model_dump_json(indent=2), encoding="utf-8"
            )
        return 0

    if args.command == "run":
        if args.unavailable:
            config = config.model_copy(update={
                "unavailable_models": [m.strip() for m in args.unavailable.split(",") if m.strip()]
            })
        decision = route(request, config)
        try:
            result = execute(request, decision, config)
        except RuntimeError as exc:
            sys.stderr.write(f"[modelpicker] error: {exc}\n")
            return 1
        if args.json:
            payload = {"decision": decision.model_dump(), "execution": result.model_dump()}
            sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        else:
            meta = f"[modelpicker] routed→{result.requested_model.value}, ran→{result.executed_model.value}"
            if result.fell_back:
                meta += f" (fell back: {result.fallback_reason})"
            if decision.needs_ultracode:
                meta += " · recommends ultracode (multi-agent)"
            meta += f", {result.latency:.1f}s"
            sys.stderr.write(meta + "\n")
            sys.stdout.write(result.output + "\n")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
