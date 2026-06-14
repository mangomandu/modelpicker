"""Savings demo — route this project's own build session and show the win.

Runs the real router (default: the `claude` CLI on your subscription) over the
actual work items from the session that built modelpicker, then reports the model
distribution and the cost saved versus running everything on Fable.

    # from the repo root, with the package importable (PYTHONPATH=src or `pip install -e .`)
    python examples/savings_demo.py

Needs the `claude` CLI (subscription) or, with judge_backend=api, an API key.
"""
from __future__ import annotations

import collections
import time

from modelpicker.config import DEFAULT_PRICE_RATES, RouterConfig
from modelpicker.models import Mode, RoutingRequest
from modelpicker.router import route

# This project's own build session, phrased as task prompts.
SESSION_TASKS = [
    ("build v1 router",        "Build a Python CLI model-routing harness: pydantic models, config, a routing policy with confidence-based escalation, and golden tests"),
    ("write golden tests",     "Write 10 deterministic golden test cases for the router, each with per-mode expected models"),
    ("subscription backend",   "Add a judge backend that shells out to the local claude CLI instead of the Anthropic API"),
    ("v2 executor + fallback", "Build an executor that runs the task on the chosen model with graceful fallback when a model is unavailable"),
    ("fix timeout bug",        "Fix the executor so a subprocess timeout raises a clean error instead of a raw traceback"),
    ("speed up the router",    "Speed up the router by disabling MCP server and tool loading on the claude CLI invocation"),
    ("rename the project",     "Rename the package, CLI, and all references from fablite to modelpicker across the whole codebase"),
    ("translate the README",   "Translate the project README into Korean, keeping the badges, mermaid diagram and tables"),
    ("drop a footer line",     "Remove the Ouroboros attribution footer line from both README files"),
    ("security review",        "Review the codebase for security issues like command injection, hardcoded secrets, and unsafe deserialization"),
    ("write savings script",   "Write a script that routes a mix of tasks and computes the cost saved versus running everything on Fable"),
    ("update READMEs for v2",  "Update the English and Korean READMEs to document the v2 run command and the fallback behavior"),
]


def main() -> None:
    cfg = RouterConfig(router_model="sonnet")
    fable_rate = DEFAULT_PRICE_RATES["fable"]
    counts: collections.Counter[str] = collections.Counter()
    baseline = routed = 0.0

    print(f"{'task':24} {'difficulty':>10} {'-> model':>10}")
    print("-" * 46)
    t0 = time.time()
    for label, prompt in SESSION_TASKS:
        d = route(RoutingRequest(mode=Mode.B, prompt=prompt), cfg)
        counts[d.selected_model.value] += 1
        baseline += d.estimated_tokens / 1e6 * fable_rate  # everything on Fable
        routed += d.estimated_cost                         # on the chosen model
        print(f"{label:24} {d.difficulty_score:10.2f} {d.selected_model.value:>10}")
    print("-" * 46)

    n = len(SESSION_TASKS)
    print(
        f"\ndistribution ({n} tasks): "
        f"sonnet={counts['sonnet']}  opus={counts['opus']}  fable={counts['fable']}"
    )
    print(f"cost saved vs all-Fable: {(1 - routed / baseline) * 100:.0f}%")
    print(f"(routed {n} tasks in {time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
