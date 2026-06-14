"""MCP server — exposes modelpicker's route/run as tools for Claude Code (or any MCP client).

Run (stdio transport):
    python -m modelpicker.mcp_server      # after: pip install -e ".[mcp]"

Register in Claude Code (.mcp.json or your MCP config):
    {"mcpServers": {"modelpicker": {"command": "modelpicker-mcp"}}}

The server is long-lived, so it pays Python startup once; each tool call just spawns
the underlying `claude` judgment/execution (subscription, no API key).
"""
from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from modelpicker import (
    Mode,
    RouterConfig,
    RoutingRequest,
    TaskType,
    execute,
)
from modelpicker import route as _route

mcp = FastMCP("modelpicker")


def _request(prompt: str, mode: str, task_type: Optional[str]) -> RoutingRequest:
    return RoutingRequest(
        mode=Mode(mode),
        prompt=prompt,
        task_type=TaskType(task_type) if task_type else None,
    )


@mcp.tool()
def route(prompt: str, mode: str = "B", task_type: Optional[str] = None) -> dict[str, Any]:
    """Judge a coding task's difficulty and pick the right model tier — decision only, no execution.

    Args:
        prompt: the task description.
        mode: "A" (Opus vs Fable) or "B" (Sonnet vs Opus vs Fable). Default "B".
        task_type: one of code_generation | refactor | debug | documentation (optional).

    Returns the RoutingDecision: selected_model, reasoning, difficulty_score, confidence,
    escalated, needs_ultracode, alternatives, estimated_tokens/cost, latency.
    """
    return _route(_request(prompt, mode, task_type), RouterConfig()).model_dump()


@mcp.tool()
def run(
    prompt: str,
    mode: str = "B",
    task_type: Optional[str] = None,
    unavailable: Optional[str] = None,
) -> dict[str, Any]:
    """Route a task, then execute it on the chosen model with graceful fallback.

    Args:
        prompt: the task description.
        mode: "A" or "B" (default "B").
        task_type: optional task category.
        unavailable: comma-separated models to skip right now, e.g. "fable" while Fable is closed.

    Returns {"decision": <RoutingDecision>, "execution": {executed_model, fell_back, output, ...}}.
    """
    cfg = RouterConfig()
    if unavailable:
        cfg = cfg.model_copy(
            update={"unavailable_models": [m.strip() for m in unavailable.split(",") if m.strip()]}
        )
    req = _request(prompt, mode, task_type)
    decision = _route(req, cfg)
    result = execute(req, decision, cfg)
    return {"decision": decision.model_dump(), "execution": result.model_dump()}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
