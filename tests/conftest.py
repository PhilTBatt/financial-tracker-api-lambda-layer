import pytest
import boto3
from moto import mock_aws

@pytest.fixture
def setup_db():
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="eu-north-1")
        table = dynamodb.create_table(
            TableName="TestTable",
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST"
        )
        yield table