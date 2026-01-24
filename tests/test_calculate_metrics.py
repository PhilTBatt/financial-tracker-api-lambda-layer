from decimal import Decimal
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
    assert m["total_spent"] == 34.80
    assert m["date_range_label"] == "Jul 2025 – Aug 2025"
    assert m["avg_monthly_spend"] == 17.40

    assert m["top_category"] == "Shopping"
    assert m["top_category_spent"] == 20.00

    assert m["monthly_spend_history"] == [
        {"period": "2025-07", "amount": 24.80},
        {"period": "2025-08", "amount": 10.00}
    ]