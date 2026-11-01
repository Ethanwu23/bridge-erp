#!/usr/bin/env python3
"""Rule-parser accuracy over the 50-question evaluation set."""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from bridge.query.parser import parse  # noqa: E402

TODAY = date(2026, 11, 1)


def main() -> int:
    path = ROOT / "eval" / "questions.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    ok = 0
    fails = []
    for row in rows:
        plan = parse(row["question"], TODAY)
        if plan["metric"] == row["expected_metric"]:
            ok += 1
        else:
            fails.append((row["id"], row["question"], row["expected_metric"], plan["metric"]))

    accuracy = ok / len(rows)
    print(f"解析准确率：{ok}/{len(rows)} = {accuracy:.1%}")
    for fid, q, exp, got in fails:
        print(f"  #{fid:<3} {q:<24} 期望={exp:<20} 实际={got}")
    return 0 if accuracy >= 0.9 else 1


if __name__ == "__main__":
    raise SystemExit(main())
