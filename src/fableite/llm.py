"""Live router judgment via the Anthropic SDK.

This is the only non-deterministic part. Golden tests inject a fixture instead,
so neither the anthropic package nor an API key is needed to run the suite.
"""
from __future__ import annotations

from .config import RouterConfig
from .constants import MODEL_IDS
from .models import RoutingRequest, RouterJudgment

_JUDGE_SYSTEM = (
    "You are a routing classifier for coding tasks. Estimate how hard the task is "
    "and how confident you are in that estimate. difficulty_score and confidence are "
    "floats in [0, 1]; higher difficulty means a more capable model is warranted. "
    "Be calibrated and concise."
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


def default_judge(request: RoutingRequest, config: RouterConfig) -> RouterJudgment:
    """Call the configured router model to judge the task. Requires ANTHROPIC_API_KEY."""
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
