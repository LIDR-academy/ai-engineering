"""Score acceptance criteria against a saved S12 agent trace."""

from __future__ import annotations

import re
import sys
from pathlib import Path


def score(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    searches = re.findall(r"action:\s+search_budgets\(", text)
    calcs = re.findall(r"action:\s+calculate_estimate\(", text)
    steps = re.findall(r"^STEP (\d+)$", text, re.M)
    reasonings = re.findall(r"reasoning:\s+(.*(?:\n(?!  action:).*)*)", text)
    # simpler: collect lines after reasoning until action
    blocks = re.split(r"\n(?=STEP \d+\n)", text.split("--- RESULT ---")[0].strip())
    incomplete = []
    empty_reasoning = 0
    for block in blocks:
        if not block.startswith("STEP"):
            continue
        if not all(k in block for k in ("reasoning:", "action:", "observation:")):
            incomplete.append(block.splitlines()[0])
            continue
        m = re.search(r"reasoning:\s+(.*?)\n  action:", block, re.S)
        reasoning = (m.group(1).strip() if m else "")
        if reasoning in {"—", "-", ""}:
            empty_reasoning += 1

    comps = re.findall(r'"estimated_hours":\s*([\d.]+)', text)
    total_m = re.search(r'"total_hours":\s*([\d.]+)', text)
    total = float(total_m.group(1)) if total_m else None
    summed = round(sum(float(x) for x in comps), 1) if comps else None

    calc_m = re.search(r"calculate_estimate\(components=\[(.*)\]\)", text)
    calc_has_refs = bool(calc_m and "[" in calc_m.group(1) and re.search(r"\[\d", calc_m.group(1)))

    print(f"file: {path}")
    print(f"steps: {len(steps)}")
    print(f"search_budgets: {len(searches)}  PASS={len(searches) > 1}")
    print(f"calculate_estimate: {len(calcs)}  PASS={len(calcs) >= 1}")
    print(f"calc includes reference_amounts: {calc_has_refs}")
    print(f"status done: {'status: done' in text}")
    print(f"incomplete steps: {incomplete or 'none'}")
    print(f"empty reasoning steps: {empty_reasoning}")
    print(f"components: {len(comps)} total={total} sum={summed} coherent={total is not None and summed is not None and abs(total - summed) < 0.2}")
    print(
        "ACCEPTANCE:",
        all(
            [
                len(searches) > 1,
                len(calcs) >= 1,
                calc_has_refs,
                "status: done" in text,
                not incomplete,
                empty_reasoning == 0,
                total is not None and summed is not None and abs(total - summed) < 0.2,
                len(comps) > 1,
            ]
        ),
    )


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "exercises/session-12/verification_trace_complex.txt")
    score(target)
