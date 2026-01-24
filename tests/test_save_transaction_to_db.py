from lambda_function import save_transactions_to_db
import pandas as pd
from decimal import Decimal

def test_save_transactions_to_db(setup_db):

    df = pd.DataFrame([
        {"date": "2026-01-01", "amount": 12.34, "payee": "Alice"},
        {"date": "2026-01-02", "amount": 56.78,  "payee": "Bob"}])
    
    metrics = {
        "total_transactions": 2,
        "total_spent": 1.0,
        "avg_monthly_spend": 10.0,
        "top_category": "Other",
        "top_category_spent": 1.0,
        "date_range_label": "Jan 2026 – Jan 2026",
        "monthly_spend_history": [{ "period": "2026-01", "amount": 1.0 }]
    }

    save_transactions_to_db(setup_db, df, metrics, '1')

    response = setup_db.scan()
    items = response.get("Items", [])

    assert len(items) == 1

    item = items[0]
    assert item["id"] == "1"
    assert "transactions" in item
    assert isinstance(item["transactions"], list)
    assert item["transactions"][0]["amount"] == 1234

    assert "metrics" in item
    assert item["metrics"]["total_transactions"] == 2
    assert item["metrics"]["total_spent"] == 100
    assert item["metrics"]["monthly_spend_history"] == [{ "period": "2026-01", "amount": 100 }]