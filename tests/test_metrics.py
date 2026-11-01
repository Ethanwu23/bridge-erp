"""Smoke tests for the deterministic metric engine (no ERP needed)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from bridge.adapter.mock import MockERPClient  # noqa: E402
from bridge.metrics.engine import compute_metric, load_metrics  # noqa: E402

PERIOD = ("2026-10-01", "2026-10-31")
AS_OF = "2026-11-01"
EXPECTED = {
    "sales_amount": 275000.0,
    "collection_amount": 160000.0,
    "collection_rate": 0.5818181818181818,
    "order_count": 5.0,
    "overdue_receivable": 80000.0,
}


def test_metrics_match_expected():
    client = MockERPClient()
    metrics = {m["code"]: m for m in load_metrics(ROOT / "config" / "metrics")}
    assert set(metrics) == set(EXPECTED), "指标配置应为 5 个"

    for code, expected in EXPECTED.items():
        out = compute_metric(client, metrics[code], *PERIOD, AS_OF)
        assert out["value"] == expected, f"{code}: {out['value']} != {expected}"
        print(f"ok  {code:<20} {out['value']}")


def test_overdue_only_past_due():
    client = MockERPClient()
    metric = next(m for m in load_metrics(ROOT / "config" / "metrics") if m["code"] == "overdue_receivable")
    out = compute_metric(client, metric, *PERIOD, AS_OF)
    # INV-002/005 未到期、INV-001/004 已收完、CN 无到期日，均不应计入
    assert out["details"]["inv"] == 2, out["details"]
    print("ok  overdue 只统计已到期 2 张")


def test_rate_allows_cross_period():
    client = MockERPClient()
    metric = next(m for m in load_metrics(ROOT / "config" / "metrics") if m["code"] == "collection_rate")
    out = compute_metric(client, metric, *PERIOD, AS_OF)
    # 分子含 PE-004（对应 9 月发票），分母只含 10 月开票
    assert abs(out["value"] - 160000 / 275000) < 1e-12
    print("ok  rate 跨期回款按回款日期计入分子")


if __name__ == "__main__":
    test_metrics_match_expected()
    test_overdue_only_past_due()
    test_rate_allows_cross_period()
    print("all tests passed")
