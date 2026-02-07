from lambda_function import calculate_metrics
import pandas as pd

def test_calculate_metrics():
    df = pd.DataFrame([
        {"date": "2025-07-31", "amount": -4.80, "description": "EAST LEEDS SNOOKER CLU (VIA GOOGLE PAY), ON 30-07-2025, 4.80"},
        {"date": "2025-07-15", "amount": -20.00, "description": "TESCO STORES"},
        {"date": "2025-08-02", "amount": -10.00, "description": "AMAZON"},
        {"date": "2025-08-05", "amount": 1000.00, "description": "SALARY"}
    ])

    m = calculate_metrics(df)

    assert m["total_transactions"] == 4
    assert m["date_range_label"] == "Jul 2025 – Aug 2025"

    assert m["monthly"]["labels"] == ["2025-07", "2025-08"]
    assert m["monthly"]["in"] == [0.0, 1000.0]
    assert m["monthly"]["out"] == [24.80, 10.00]
    assert m["monthly"]["avgOut"] == (24.80 + 10.00) / 2

    assert m["monthly"]["byCategoryOut"] == {
        "Entertainment": [4.80, 0.0],
        "Groceries": [20.00, 0.0],
        "Online Shopping": [0.0, 10.00],
    }

    assert m["weekly"]["labels"] == ["2025-W29", "2025-W31", "2025-W32"]
    assert m["weekly"]["in"] == [0.0, 0.0, 1000.0]
    assert m["weekly"]["out"] == [20.00, 14.80, 0.0]
    assert m["weekly"]["avgOut"] == (20.00 + 14.80 + 0.0) / 3

    assert m["weekly"]["byCategoryOut"] == {
        "Entertainment": [0.0, 4.80, 0.0],
        "Groceries": [20.00, 0.0, 0.0],
        "Online Shopping": [0.0, 10.00, 0.0],
    }

    assert m["buckets"]["outgoingSize"]["labels"] == ["£0–5", "£5–10", "£10–25", "£25–50", "£50–100", "£100–250", "£250–500", "£500+"]
    assert m["buckets"]["outgoingSize"]["counts"] == [1, 0, 2, 0, 0, 0, 0, 0]

    assert m["buckets"]["incomingSize"]["labels"] == ["£0–5", "£5–10", "£10–25", "£25–50", "£50–100", "£100–250", "£250–500", "£500+"]
    assert m["buckets"]["incomingSize"]["counts"] == [0, 0, 0, 0, 0, 0, 0, 1]

    assert m["categories"]["out_total_by_category"] == {
        "Entertainment": 4.80,
        "Groceries": 20.00,
        "Online Shopping": 10.00,
    }

    assert m["categories"]["out_count_by_category"] == {
        "Entertainment": 1,
        "Groceries": 1,
        "Online Shopping": 1,
    }

    assert m["categories"]["avg_out_by_category"] == {
        "Entertainment": 4.80,
        "Groceries": 20.00,
        "Online Shopping": 10.00,
    }

    assert m["categories"]["out_size_buckets_by_category"]["labels"] == ["£0–5", "£5–10", "£10–25", "£25–50", "£50–100", "£100–250", "£250–500", "£500+"]
    assert m["categories"]["out_size_buckets_by_category"]["counts"] == {
        "Entertainment": [1, 0, 0, 0, 0, 0, 0, 0],
        "Groceries": [0, 0, 1, 0, 0, 0, 0, 0],
        "Online Shopping": [0, 0, 1, 0, 0, 0, 0, 0]
    }