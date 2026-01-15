import boto3
from moto import mock_aws
from lambda_function import save_transactions_to_db
import pandas as pd
from decimal import Decimal

@mock_aws
def test_save_transactions_to_db():
    dynamodb = boto3.resource("dynamodb", region_name="eu-north-1")
    table = dynamodb.create_table(
        TableName="TestTable",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST"
    )

    df = pd.DataFrame([
        {"date": "2026-01-01", "amount": 12.34, "memo": "test", "payee": "Alice"},
        {"date": "2026-01-02", "amount": 56.78, "memo": "test2", "payee": "Bob"}])

    save_transactions_to_db(table, df)

    response = table.scan()
    items = response.get("Items", [])

    assert len(items) == 1

    item = items[0]

    assert "id" in item
    assert "transactions" in item
    assert isinstance(item["transactions"], list)
    assert item["transactions"][0]["amount"] == Decimal("12.34")