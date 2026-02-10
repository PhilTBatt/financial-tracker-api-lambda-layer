from lambda_function import save_transactions_to_db
import pandas as pd

def test_save_transactions_to_db(setup_db):
    df = pd.DataFrame([
        {"date": "2026-01-01", "amount": 12.34, "description": "Alice"},
        {"date": "2026-01-02", "amount": 56.78, "description": "Bob"},
        {"date": "2026-01-10", "amount": -600.00, "description": "BIG PURCHASE"}
    ])

    metrics = {
        "total_transactions": 3,
        "date_range_label": "Jan 2026 – Jan 2026",

        "avg_monthly_spend": 600.0,
        "avg_weekly_spend": 200.0, 

        "monthly": {
            "labels": ["2026-01"],
            "in": [69.12],
            "out": [600.0],
            "avgOut": 600.0,
            "byCategoryOut": {"Other": [600.0]}
        },
        "weekly": {
            "labels": ["2025-W53", "2026-W01", "2026-W02"],
            "in": [12.34, 56.78, 0.0],
            "out": [0.0, 0.0, 600.0],
            "avgOut": 200.0,
            "byCategoryOut": {"Other": [0.0, 0.0, 600.0]}
        },
        "categories": {
            "out_total_by_category": {"Other": 600.0},
            "out_count_by_category": {"Other": 1},
            "avg_out_by_category": {"Other": 600.0},
            "out_size_buckets_by_category": {
                "labels": ["£0–5", "£5–10", "£10–25", "£25–50", "£50–100", "£100–250", "£250–500", "£500+"],
                "counts": {"Other": [0, 0, 0, 0, 0, 0, 0, 1]}
            }
        },
        "buckets": {
            "outgoingSize": {
                "labels": ["£0–5", "£5–10", "£10–25", "£25–50", "£50–100", "£100–250", "£250–500", "£500+"],
                "counts": [0, 0, 0, 0, 0, 0, 0, 1]
            },
            "incomingSize": {
                "labels": ["£0–5", "£5–10", "£10–25", "£25–50", "£50–100", "£100–250", "£250–500", "£500+"],
                "counts": [0, 0, 1, 0, 0, 0, 0, 0]
            }
        },
        "daily": {
            "labels": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09", "2026-01-10"],
            "out":    [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 600.0],
            "in":     [12.34, 56.78, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        },
        "rollingOut7d": {
            "window": 7,
            "values": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 85.71428571428571]
        },
        "topOutgoingTransactions": [
            {"date": "2026-01-10", "amount": -600.00, "description": "BIG PURCHASE"}
        ]
    }

    save_transactions_to_db(setup_db, df, metrics, "1")

    response = setup_db.scan()
    items = response.get("Items", [])
    assert len(items) == 1

    item = items[0]
    assert item["id"] == "1"

    assert item["transactions"][0]["amount"] == 1234
    assert item["transactions"][1]["amount"] == 5678
    assert item["transactions"][2]["amount"] == -60000

    assert item["metrics"]["totalTransactions"] == 3
    assert item["metrics"]["dateRangeLabel"] == "Jan 2026 – Jan 2026"

    assert item["metrics"]["avgMonthlySpend"] == 60000
    assert item["metrics"]["avgWeeklySpend"] == 20000

    assert item["metrics"]["monthly"]["in"] == [6912]
    assert item["metrics"]["monthly"]["out"] == [60000]

    assert item["metrics"]["weekly"]["in"] == [1234, 5678, 0]
    assert item["metrics"]["weekly"]["out"] == [0, 0, 60000]

    assert item["metrics"]["categories"]["outTotalByCategory"] == {"Other": 60000}
    assert item["metrics"]["categories"]["outCountByCategory"] == {"Other": 1}
    assert item["metrics"]["categories"]["avgOutByCategory"] == {"Other": 60000}
    assert item["metrics"]["categories"]["outSizeBucketsByCategory"]["counts"] == {"Other": [0, 0, 0, 0, 0, 0, 0, 1]}

    assert item["metrics"]["buckets"]["outgoingSize"]["counts"] == [0, 0, 0, 0, 0, 0, 0, 1]
    assert item["metrics"]["buckets"]["incomingSize"]["counts"] == [0, 0, 1, 0, 0, 0, 0, 0]

    assert item["metrics"]["daily"]["labels"][0] == "2026-01-01"
    assert item["metrics"]["daily"]["out"][-1] == 60000
    assert item["metrics"]["daily"]["in"][0] == 1234
    assert item["metrics"]["daily"]["in"][1] == 5678

    assert item["metrics"]["rollingOut7d"]["window"] == 7
    assert len(item["metrics"]["rollingOut7d"]["values"]) == len(item["metrics"]["daily"]["labels"])
    assert item["metrics"]["rollingOut7d"]["values"][-1] == 8571

    assert item["metrics"]["topOutgoingTransactions"][0]["date"] == "2026-01-10"
    assert item["metrics"]["topOutgoingTransactions"][0]["amount"] == -60000
    assert item["metrics"]["topOutgoingTransactions"][0]["description"] == "BIG PURCHASE"