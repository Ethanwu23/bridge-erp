#!/usr/bin/env python3
"""D1 checklist runner.

Usage:
  python scripts/d1_check.py --mode mock
  python scripts/d1_check.py --mode http --base-url http://localhost:8080 \
      --key <api_key> --secret <api_secret>

Checks:
  1 ERPNext reachable
  2 API token works
  3 seed data present
  4 five metrics match expected values
  5 DeepSeek JSON call
  6 metric config + baseline doc in place
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from bridge.adapter.http_client import HttpERPClient, ERPError  # noqa: E402
from bridge.adapter.mock import MockERPClient  # noqa: E402
from bridge.metrics.engine import compute_metric, load_metrics  # noqa: E402

PERIOD = ("2026-10-01", "2026-10-31")
AS_OF = "2026-11-01"
EXPECTED = {
    "sales_amount": 275000.0,
    "collection_amount": 160000.0,
    "collection_rate": 0.5818181818,
    "order_count": 5.0,
    "overdue_receivable": 80000.0,
}
TOL = {"collection_rate": 1e-4}
DEFAULT_TOL = 0.01


def check_erp(client, mode: str) -> tuple[str, str]:
    try:
        ok = client.ping()
    except ERPError as exc:
        return "FAIL", str(exc)[:120]
    if mode == "mock":
        return "SKIP", "mock 模式无真实 ERP（缺 Docker）"
    return ("PASS" if ok else "FAIL"), "ping pong" if ok else "ping 返回异常"


def check_token(client, mode: str) -> tuple[str, str]:
    if mode == "mock":
        return "SKIP", "mock 模式无 Token"
    try:
        rows = client.list_resource("Sales Invoice", [], ["name"], 0, 1)
    except ERPError as exc:
        return "FAIL", str(exc)[:120]
    return "PASS", f"取到 {len(rows)} 条发票"


def check_seed(client, mode: str) -> tuple[str, str]:
    counts = {}
    for doctype in ("Sales Invoice", "Payment Entry", "Sales Order"):
        rows = client.list_resource(doctype, [], ["name"], 0, 1000)
        counts[doctype] = len(rows)
    if mode == "mock":
        ok = counts == {"Sales Invoice": 7, "Payment Entry": 4, "Sales Order": 5}
        return ("PASS" if ok else "FAIL"), json.dumps(counts, ensure_ascii=False)
    ok = counts["Sales Invoice"] > 0
    return ("PASS" if ok else "FAIL"), json.dumps(counts, ensure_ascii=False)


def check_metrics(client) -> tuple[str, str, list[dict]]:
    metrics = load_metrics(ROOT / "config" / "metrics")
    results = []
    failures = []
    for metric in metrics:
        out = compute_metric(client, metric, *PERIOD, AS_OF)
        expected = EXPECTED.get(metric["code"])
        tol = TOL.get(metric["code"], DEFAULT_TOL)
        ok = expected is not None and out["value"] is not None and abs(out["value"] - expected) <= tol
        out["expected"] = expected
        out["ok"] = ok
        results.append(out)
        if not ok:
            failures.append(metric["code"])
    status = "PASS" if not failures else "FAIL"
    detail = "5/5 与期望值一致" if not failures else f"不一致: {', '.join(failures)}"
    return status, detail, results


def check_llm() -> tuple[str, str]:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        return "SKIP", "未设置 DEEPSEEK_API_KEY"
    payload = {
        "model": "deepseek-flash",
        "messages": [
            {"role": "system", "content": "只输出 JSON，不要解释。"},
            {
                "role": "user",
                "content": '把问题映射为指标：{"metric":"sales_amount|collection_amount|collection_rate|order_count|overdue_receivable"}。问题：本月回款率',
            },
        ],
        "temperature": 0,
        "max_tokens": 120,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        ok = parsed.get("metric") == "collection_rate"
        return ("PASS" if ok else "FAIL"), f"返回 {content[:60]}"
    except Exception as exc:
        return "FAIL", str(exc)[:120]


def check_config() -> tuple[str, str]:
    metrics = load_metrics(ROOT / "config" / "metrics")
    baseline = ROOT.parent / "Bridge-开工前置检查-v0.1.docx"
    ok = len(metrics) == 5 and baseline.exists()
    detail = f"指标 {len(metrics)} 个；口径基线文档 {'存在' if baseline.exists() else '缺失'}"
    return ("PASS" if ok else "FAIL"), detail


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["mock", "http"], default="mock")
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--key", default="")
    parser.add_argument("--secret", default="")
    args = parser.parse_args()

    if args.mode == "http":
        client = HttpERPClient(args.base_url, args.key, args.secret)
    else:
        client = MockERPClient()

    rows = []
    rows.append(("1", "ERPNext 可达", *check_erp(client, args.mode)))
    rows.append(("2", "API Token 可用", *check_token(client, args.mode)))
    rows.append(("3", "种子数据齐全", *check_seed(client, args.mode)))
    status, detail, metric_rows = check_metrics(client)
    rows.append(("4", "5 个指标取数", status, detail))
    rows.append(("5", "DeepSeek JSON 调用", *check_llm()))
    rows.append(("6", "配置与口径基线", *check_config()))

    width = "{:<3}{:<20}{:<8}{}"
    print(width.format("#", "检查项", "结果", "说明"))
    for r in rows:
        print(width.format(*r))

    print("\n指标明细：")
    for m in metric_rows:
        print(
            f"  {m['code']:<20} {m['name']:<6} 计算值={m['value']:<12} 期望={m['expected']:<12} "
            f"{'OK' if m['ok'] else 'MISMATCH'}  记录数={m['details']}"
        )

    failed = [r for r in rows if r[2] == "FAIL"]
    print(f"\n结果：{len(rows) - len(failed)} 项通过/跳过，{len(failed)} 项失败")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
