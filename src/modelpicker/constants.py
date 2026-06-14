"""Static tables: short model names -> full IDs, and per-mode tier order."""
from __future__ import annotations

# Short execution-model names -> full Anthropic model IDs (the v2 executor will
# need these; v1 decisions only carry the short names).
MODEL_IDS: dict[str, str] = {
    "haiku": "claude-haiku-4-5",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-8",
    "fable": "claude-fable-5",
}

# Per-mode execution tier order, lowest capability/cost -> highest.
# Mode A: opus < fable.  Mode B: sonnet < opus < fable.
TIER_ORDER: dict[str, list[str]] = {
    "A": ["opus", "fable"],
    "B": ["sonnet", "opus", "fable"],
}

# Effort levels, lowest -> highest (matches Claude Code / API ordering).
EFFORT_ORDER: list[str] = ["low", "medium", "high", "xhigh", "max"]

# Effort levels each execution model supports (Claude Code model-config docs):
# Sonnet 4.6 has no xhigh; Opus 4.8 and Fable 5 support the full set. A level the
# model lacks is clamped down to the highest supported level at or below it.
MODEL_EFFORT_SUPPORT: dict[str, list[str]] = {
    "sonnet": ["low", "medium", "high", "max"],
    "opus": ["low", "medium", "high", "xhigh", "max"],
    "fable": ["low", "medium", "high", "xhigh", "max"],
}

# Flags that make a one-shot `claude -p` call start faster. Neither the difficulty
# judgment nor the v1 plain-prompt executor needs MCP servers or tools, so skip
# loading them: --strict-mcp-config + empty config drops MCP startup (~2s), and
# --allowedTools "" / --disallowedTools drops the tool set (~0.4s more).
# Measured warm latency: ~5.0s -> ~3.4s per call.
CLAUDE_FAST_FLAGS: list[str] = [
    "--strict-mcp-config",
    "--mcp-config",
    '{"mcpServers":{}}',
    "--allowedTools",
    "",
    "--disallowedTools",
    "Bash,Read,Write,Edit,Glob,Grep,WebFetch,WebSearch,Task,TodoWrite",
]
