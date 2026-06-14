"""Router-model judgment — the only non-deterministic part of the router.

Two backends (selected by RouterConfig.judge_backend):

  * "claude_cli" (default) — shells out to the local `claude` CLI, which runs on
    your Claude subscription. No API key, no separate API billing.
  * "api" — the Anthropic SDK (needs ANTHROPIC_API_KEY or an `ant auth login` profile).

Golden tests inject a fixture instead of calling either backend, so the suite needs
neither the `claude` CLI nor the `anthropic` package nor any credentials.
"""
from __future__ import annotations

import json
import subprocess

from .config import RouterConfig
from .constants import MODEL_IDS
from .models import RoutingRequest, RouterJudgment

_JUDGE_SYSTEM = (
    "You are a routing classifier for coding tasks. Estimate how hard the task is "
    "and how confident you are in that estimate. difficulty_score and confidence are "
    "floats in [0, 1]; higher difficulty means a more capable model is warranted. "
    "Be calibrated and concise."
)

_JSON_INSTRUCTION = (
    "Respond with ONLY a compact JSON object, no prose and no code fence:\n"
    '{"difficulty_score": <float 0..1>, "confidence": <float 0..1>, "reasoning": "<short>"}'
)


def _render_task(request: RoutingRequest) -> str:
    parts = [
        f"Task type: {request.task_type.value if request.task_type else 'unspecified'}",
        f"Prompt:\n{request.prompt}",
    ]
    cc = request.code_context
    if cc is not None:
        if cc.raw_text:
            parts.append(f"Code context:\n{cc.raw_text}")
        else:
            meta = {
                k: v
                for k, v in cc.model_dump(exclude_none=True).items()
                if k != "raw_text"
            }
            if meta:
                parts.append(f"Code context (structured): {meta}")
    return "\n\n".join(parts)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _parse_judgment(text: str) -> RouterJudgment:
    """Extract the outermost JSON object from model output and validate it."""
    raw = text.strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise RuntimeError(f"Router judgment was not JSON: {raw[:200]!r}")
    data = json.loads(raw[start : end + 1])
    reasoning = str(data.get("reasoning") or "").strip() or "router judgment"
    return RouterJudgment(
        difficulty_score=_clamp01(float(data["difficulty_score"])),
        confidence=_clamp01(float(data["confidence"])),
        reasoning=reasoning,
    )


def cli_judge(request: RoutingRequest, config: RouterConfig) -> RouterJudgment:
    """Judge via the local `claude` CLI (subscription auth; no API key)."""
    prompt = f"{_JUDGE_SYSTEM}\n\n{_render_task(request)}\n\n{_JSON_INSTRUCTION}"
    cmd = ["claude", "-p", prompt, "--model", config.router_model]
    try:
        proc = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=config.judge_timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "`claude` CLI not found on PATH. Install the Claude Code CLI and log in, "
            "or set judge_backend: api with ANTHROPIC_API_KEY."
        ) from exc
    if proc.returncode != 0:
        raise RuntimeError(
            f"`claude` CLI failed (exit {proc.returncode}): {proc.stderr.strip()}"
        )
    return _parse_judgment(proc.stdout)


def api_judge(request: RoutingRequest, config: RouterConfig) -> RouterJudgment:
    """Judge via the Anthropic SDK. Requires ANTHROPIC_API_KEY / an auth profile."""
    import anthropic  # imported lazily

    client = anthropic.Anthropic()
    model_id = MODEL_IDS.get(config.router_model, config.router_model)
    resp = client.messages.parse(
        model=model_id,
        max_tokens=1024,
        system=_JUDGE_SYSTEM,
        messages=[{"role": "user", "content": _render_task(request)}],
        output_format=RouterJudgment,
    )
    parsed = resp.parsed_output
    if parsed is None:
        raise RuntimeError("Router model did not return a structured judgment")
    return parsed


def judge(request: RoutingRequest, config: RouterConfig) -> RouterJudgment:
    """Dispatch to the configured judgment backend."""
    if config.judge_backend == "api":
        return api_judge(request, config)
    return cli_judge(request, config)
