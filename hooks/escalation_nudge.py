#!/usr/bin/env python3
"""UserPromptSubmit hook (v2): pre-flight escalation nudge via the modelpicker judge.

Default effort is xhigh on Opus. Before a turn runs, this asks modelpicker's
`route` (an LLM judge — smarter than keywords, catches subtle-hard prompts) what
the task actually needs. If that's an UPGRADE over your current model/effort
(or it warrants ultracode), it prints a non-blocking nudge so you do it right the
first time instead of failing at xhigh and redoing.

Cost: the judge runs `claude -p` (~3s on subscription) per *substantive* prompt.
A cheap prefilter skips obvious-trivial prompts so greetings/typo-fixes stay
instant. Never blocks; any error -> stays quiet. Edit MP_DIR / ASSUMED_MODEL /
FABLE_AVAILABLE / prefilter below to tune.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

MP_DIR = "/home/dlfnek/projects/modelpicker"  # where the modelpicker package lives
ASSUMED_MODEL = "opus"        # your usual main model (no $CLAUDE_MODEL env exists)
FABLE_AVAILABLE = False       # flip to True when Fable opens to your account
JUDGE_TIMEOUT = 25            # seconds; hook's own timeout in settings should be >= this

EFFORT_RANK = {"low": 0, "medium": 1, "high": 2, "xhigh": 3, "max": 4}
MODEL_RANK = {"sonnet": 0, "opus": 1, "fable": 2}

# Cheap skip: obvious-trivial prompts never need escalation -> don't spend a judge
# call (keeps them instant). Conservative: a wrong skip just means "no nudge".
TRIVIAL_SKIP = re.compile(
    r"^\s*(ok|okay|ㅇㅋ|응|넵|네|굿|좋아|thanks|thank you|ty|고마워\w*|감사\w*|수고\w*)\b"
    r"|오타|rename|이름\s*(을)?\s*바꿔|포맷팅?|주석\s*(을)?\s*(달|추가)|한\s*줄\s*추가",
    re.IGNORECASE,
)


def _route(prompt: str) -> dict | None:
    try:
        proc = subprocess.run(
            ["uv", "run", "--project", MP_DIR, "--quiet",
             "modelpicker", "route", "--mode", "B", "--prompt", prompt],
            capture_output=True, text=True, timeout=JUDGE_TIMEOUT,
        )
        if proc.returncode != 0:
            return None
        return json.loads(proc.stdout)
    except Exception:
        return None


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    prompt = (data.get("prompt") or "").strip()
    if not prompt or TRIVIAL_SKIP.search(prompt):
        return 0  # empty or obvious-trivial -> instant, no judge

    cur_eff = os.environ.get("CLAUDE_EFFORT", "xhigh")
    cur_eff_rank = EFFORT_RANK.get(cur_eff, 3)

    d = _route(prompt)
    if not d:
        return 0  # judge unavailable/timeout -> never break the prompt

    model = d.get("selected_model", ASSUMED_MODEL)
    effort = d.get("effort", cur_eff)
    ultra = bool(d.get("needs_ultracode"))
    diff = d.get("difficulty_score")

    parts: list[str] = []
    degraded = False
    # model upgrade?
    if MODEL_RANK.get(model, 1) > MODEL_RANK.get(ASSUMED_MODEL, 1):
        if model == "fable" and not FABLE_AVAILABLE:
            # fable closed -> go as deep as available (max); ultracode is added below
            # only if route actually flagged breadth (needs_ultracode), not for a
            # single deep problem like a race-condition hunt.
            degraded = True
            if EFFORT_RANK.get("max", 4) > cur_eff_rank:
                parts.append("`/effort max`")
        else:
            parts.append(f"`/model {model}`" + (f" + `/effort {effort}`"
                         if EFFORT_RANK.get(effort, 3) > cur_eff_rank else ""))
    # effort upgrade (same model)?
    elif EFFORT_RANK.get(effort, cur_eff_rank) > cur_eff_rank:
        parts.append(f"`/effort {effort}`")

    if ultra:
        parts.append("프롬프트에 `ultracode`")

    if not parts:
        return 0  # route agrees current setup is fine -> stay quiet

    reason = (d.get("reasoning") or "").strip()
    if len(reason) > 90:
        reason = reason[:87] + "…"
    diff_s = f"난이도 {diff:.2f}" if isinstance(diff, (int, float)) else ""
    pre = "fable 막힘→차선 " if degraded else ""
    head = f"💡 ({pre}지금 {ASSUMED_MODEL}/{cur_eff}) modelpicker 추천: " + " + ".join(parts)
    tail = f"  ({diff_s})" if diff_s else ""
    print(json.dumps({"systemMessage": head + tail + (f"\n   ↳ {reason}" if reason else "")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
