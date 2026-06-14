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
