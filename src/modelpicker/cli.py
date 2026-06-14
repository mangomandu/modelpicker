"""modelpicker CLI — `modelpicker route ...` prints a RoutingDecision JSON to stdout.

stdout always contains only the RoutingDecision JSON. Metrics go to --report-json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

import yaml

from .config import load_config
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="modelpicker", description="Model routing harness (v1: router-only)."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("route", help="Route a task and print a RoutingDecision JSON.")
    r.add_argument("--mode", required=True, choices=["A", "B"],
                   help="A = Opus/Fable, B = Sonnet/Opus/Fable")
    r.add_argument("--prompt", required=True, help="Task description")
    r.add_argument("--task-type", choices=[t.value for t in TaskType], default=None)
    r.add_argument("--context-file", default=None,
                   help="Path to code context (plain text, or JSON/YAML)")
    r.add_argument("--config", default=None, help="Path to a router config (JSON/YAML)")
    r.add_argument("--report-json", default=None,
                   help="Write a metrics report to this path (stdout stays decision-only)")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command != "route":
        return 1

    config = load_config(args.config)
    request = RoutingRequest(
        mode=Mode(args.mode),
        prompt=args.prompt,
        task_type=TaskType(args.task_type) if args.task_type else None,
        code_context=_load_context_file(args.context_file),
    )
    decision = route(request, config)
    sys.stdout.write(decision.model_dump_json(indent=2) + "\n")

    if args.report_json:
        # Unlabeled single CLI run -> routing_accuracy is null.
        report = build_report([decision], routing_accuracy=None)
        Path(args.report_json).write_text(
            report.model_dump_json(indent=2), encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
