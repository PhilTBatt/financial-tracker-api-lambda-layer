from lambda_function import save_transactions_to_db
import pandas as pd

def test_save_transactions_to_db(setup_db):
    df = pd.DataFrame([
        {"date": "2026-01-01", "amount": 12.34, "payee": "Alice"},
        {"date": "2026-01-02", "amount": 56.78, "payee": "Bob"},
        {"date": "2026-01-10", "amount": -600.00, "payee": "BIG PURCHASE"}
    ])

    metrics = {
        "total_transactions": 3,
        "date_range_label": "Jan 2026 – Jan 2026",
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
        "buckets": {
            "outgoingSize": {
                "labels": ["£0–5", "£5–10", "£10–25", "£25–50", "£50–100", "£100–250", "£250–500", "£500+"],
                "counts": [0, 0, 0, 0, 0, 0, 0, 1]
            },
            "incomingSize": {
                "labels": ["£0–5", "£5–10", "£10–25", "£25–50", "£50–100", "£100–250", "£250–500", "£500+"],
                "counts": [0, 0, 1, 0, 0, 0, 0, 0]
            }
        }
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

    assert item["metrics"]["total_transactions"] == 3
    assert item["metrics"]["date_range_label"] == "Jan 2026 – Jan 2026"

    assert item["metrics"]["monthly"]["in"] == [6912]
    assert item["metrics"]["monthly"]["out"] == [60000]

    assert item["metrics"]["weekly"]["in"] == [1234, 5678, 0]
    assert item["metrics"]["weekly"]["out"] == [0, 0, 60000]

    assert item["metrics"]["buckets"]["outgoingSize"]["counts"] == [0, 0, 0, 0, 0, 0, 0, 1]
    assert item["metrics"]["buckets"]["incomingSize"]["counts"] == [0, 0, 1, 0, 0, 0, 0, 0]
