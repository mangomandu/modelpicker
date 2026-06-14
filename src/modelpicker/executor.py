"""v2 executor: run the task on the chosen model, with graceful fallback.

The router (v1) only *decides* which model to use. The executor actually runs the
task on that model. If the chosen model is unavailable (e.g. Fable is closed), it
degrades one tier at a time down the mode's order (fable -> opus -> sonnet) so the
work still completes.

Two backends, same shape as the judge:
  * "claude_cli" (default) — `claude -p <task> --model <model>` on your subscription.
  * "api" — the Anthropic SDK.
Tests inject a fake runner, so no live model is called.
"""
from __future__ import annotations

import subprocess
import time
from typing import Callable, Optional

from .config import RouterConfig
from .constants import CLAUDE_FAST_FLAGS, MODEL_IDS, TIER_ORDER
from .models import ExecModel, ExecutionResult, Mode, RoutingDecision, RoutingRequest

# What to pass to `claude --model`. Aliases work for the everyday tiers; Fable
# needs its full id.
_CLI_MODEL = {"haiku": "haiku", "sonnet": "sonnet", "opus": "opus", "fable": "claude-fable-5"}

Runner = Callable[[str, str, RouterConfig], str]


class ModelUnavailable(RuntimeError):
    """Raised by a runner when the requested model can't run (triggers fallback)."""


def _task_prompt(request: RoutingRequest) -> str:
    parts = [request.prompt]
    cc = request.code_context
    if cc is not None:
        if cc.raw_text:
            parts.append(f"\n\nContext:\n{cc.raw_text}")
        else:
            meta = {
                k: v for k, v in cc.model_dump(exclude_none=True).items() if k != "raw_text"
            }
            if meta:
                parts.append(f"\n\nContext: {meta}")
    return "".join(parts)


def _fallback_chain(mode: Mode, selected: str, config: RouterConfig) -> list[str]:
    """[selected, one tier down, ..., lowest] — or just [selected] if fallback is off."""
    tiers = TIER_ORDER[mode.value]
    i = tiers.index(selected)
    return list(reversed(tiers[: i + 1])) if config.executor_fallback else [selected]


def cli_runner(task: str, model: str, config: RouterConfig) -> str:
    """Run the task on the local `claude` CLI (subscription)."""
    cli_model = _CLI_MODEL.get(model, model)
    cmd = ["claude", "-p", task, "--model", cli_model, *CLAUDE_FAST_FLAGS]
    try:
        proc = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=config.execute_timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "`claude` CLI not found; install it / log in, or set executor_backend: api."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        # A timeout isn't "model unavailable" — a smaller model won't be faster on a
        # too-big task — so surface it cleanly rather than falling back.
        raise RuntimeError(
            f"execution timed out after {config.execute_timeout_seconds}s on {model} "
            "(task may be too large — raise execute_timeout_seconds or narrow the task)."
        ) from exc
    if proc.returncode != 0:
        # Treat any failure as "this model couldn't run" so the chain can fall back.
        raise ModelUnavailable(f"{model}: {proc.stderr.strip() or 'claude CLI error'}")
    return proc.stdout.strip()


def api_runner(task: str, model: str, config: RouterConfig) -> str:
    """Run the task via the Anthropic SDK. Requires ANTHROPIC_API_KEY."""
    import anthropic

    client = anthropic.Anthropic()
    model_id = MODEL_IDS.get(model, model)
    try:
        resp = client.messages.create(
            model=model_id,
            max_tokens=8000,
            messages=[{"role": "user", "content": task}],
        )
    except Exception as exc:  # not-found / unavailable / overloaded -> fall back
        raise ModelUnavailable(f"{model}: {exc}") from exc
    return "".join(
        b.text for b in resp.content if getattr(b, "type", None) == "text"
    ).strip()


def run_model(task: str, model: str, config: RouterConfig) -> str:
    """Dispatch to the configured executor backend."""
    if config.executor_backend == "api":
        return api_runner(task, model, config)
    return cli_runner(task, model, config)


def execute(
    request: RoutingRequest,
    decision: RoutingDecision,
    config: Optional[RouterConfig] = None,
    runner: Optional[Runner] = None,
) -> ExecutionResult:
    """Run the task on the routed model, degrading down the tier order if needed."""
    config = config or RouterConfig()
    runner = runner or run_model
    task = _task_prompt(request)
    requested = decision.selected_model.value
    chain = _fallback_chain(request.mode, requested, config)

    reason: Optional[str] = None
    last_error: Optional[str] = None
    t0 = time.perf_counter()
    for model in chain:
        if model in config.unavailable_models:
            reason = reason or f"{model} marked unavailable"
            continue
        try:
            output = runner(task, model, config)
        except ModelUnavailable as exc:
            reason = reason or str(exc)
            last_error = str(exc)
            continue
        return ExecutionResult(
            requested_model=ExecModel(requested),
            executed_model=ExecModel(model),
            fell_back=(model != requested),
            fallback_reason=reason if model != requested else None,
            output=output,
            latency=round(time.perf_counter() - t0, 6),
        )
    raise RuntimeError(
        f"No available model in fallback chain {chain} "
        f"(unavailable={config.unavailable_models}); last error: {last_error}"
    )
