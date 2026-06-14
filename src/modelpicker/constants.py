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

# Flags that make a one-shot `claude -p` call start faster: skip loading MCP
# servers (ouroboros, etc.), which otherwise add ~2s of startup per call. Neither
# the difficulty judgment nor the v1 plain-prompt executor needs MCP tools.
# Measured: 5.0s -> 2.8s per call.
CLAUDE_FAST_FLAGS: list[str] = ["--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}']
