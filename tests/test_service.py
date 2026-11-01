"""End-to-end service test: question -> plan -> answer, against the mock ERP."""
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from bridge.adapter.mock import MockERPClient  # noqa: E402
from bridge.metrics.engine import load_metrics  # noqa: E402
from bridge.query.validator import QueryError  # noqa: E402
from bridge.service import answer  # noqa: E402

METRICS = load_metrics(ROOT / "config" / "metrics")


def test_october_questions():
    client = MockERPClient()
    today = date(2026, 10, 31)
    cases = {
        "10月销售额是多少": ("sales_amount", 275000.0, "CNY"),
        "这个月收了多少钱": ("collection_amount", 160000.0, "CNY"),
        "本月回款率": ("collection_rate", 160000 / 275000, "%"),
        "本月订单数": ("order_count", 5.0, "笔"),
    }
    for question, (metric, expected, unit) in cases.items():
        out = answer(client, question, METRICS, today=today)
        assert out["metric"] == metric, (question, out["metric"])
        assert out["unit"] == unit, (question, out["unit"])
        assert abs(out["value"] - expected) < 1e-6, (question, out["value"])
        assert out["period"] == {"from": "2026-10-01", "to": "2026-10-31"}
        assert out["explanation"].startswith(out["name"])
        print(f"ok  {question:<12} {out['name']} = {out['value']}")


def test_overdue_as_of_today():
    client = MockERPClient()
    out = answer(client, "现在逾期应收多少", METRICS, today=date(2026, 11, 1))
    assert out["metric"] == "overdue_receivable"
    assert out["value"] == 80000.0
    print("ok  逾期应收（截至 2026-11-01）= 80000")


def test_unknown_question_rejected():
    client = MockERPClient()
    try:
        answer(client, "今天天气怎么样", METRICS, today=date(2026, 11, 1))
    except QueryError as exc:
        assert exc.code == "E_NO_METRIC"
        print("ok  无指标问题被拒答 E_NO_METRIC")
        return
    raise AssertionError("应当抛出 QueryError")


if __name__ == "__main__":
    test_october_questions()
    test_overdue_as_of_today()
    test_unknown_question_rejected()
    print("all service tests passed")
