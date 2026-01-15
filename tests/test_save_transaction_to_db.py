from lambda_function import save_transactions_to_db
import pandas as pd
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def test_save_transactions_to_db(setup_db):
    logger.info("Starting test_save_transactions_to_db")

    df = pd.DataFrame([
        {"date": "2026-01-01", "amount": 12.34, "memo": "test", "payee": "Alice"},
        {"date": "2026-01-02", "amount": 56.78, "memo": "test2", "payee": "Bob"}])

    save_transactions_to_db(setup_db, df)
    logger.info("Transactions saved to DB")

    response = setup_db.scan()
    items = response.get("Items", [])

    assert len(items) == 1

    item = items[0]

    assert "id" in item
    assert "transactions" in item
    assert isinstance(item["transactions"], list)
    assert item["transactions"][0]["amount"] == Decimal("12.34")