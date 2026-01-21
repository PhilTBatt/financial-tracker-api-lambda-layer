import os
import io
import logging
import boto3
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timezone
from decimal import Decimal
from qifparse.parser import QifParser
from urllib.parse import unquote_plus

os.environ['MPLCONFIGDIR'] = '/tmp/matplotlib'

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('financial-app-db')

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    record = event['Records'][0]
    bucket_name = record['s3']['bucket']['name']
    raw_key = record['s3']['object']['key']
    object_key = unquote_plus(raw_key)
    

    key = object_key[len('upload/'):] if object_key.startswith('upload/') else object_key
    i = key.find("_")
    db_id = key[:i] if i != -1 else key

    logger.info(f"File uploaded: {object_key} in bucket: {bucket_name}")

    response = s3.get_object(Bucket=bucket_name, Key=object_key)
    file_contents = response['Body'].read().decode('utf-8')
    qifFile = QifParser.parse(io.StringIO(file_contents))

    try:
        df = process_file(qifFile)
        if df.empty:
            logger.error("No transactions found in QIF file.")
            return
        logger.info(f"File parsed successfully with {len(df)} transactions.")
    except Exception as e:
        logger.error(f"Error processing order: {str(e)}")
        raise

    try:
        save_transactions_to_db(table, df, db_id)
        logger.info(f"DF saved to DB.")
    except Exception as e:
        logger.error(f"Error saving infomation to database: {str(e)}")
        raise

def process_file(qifFile):
    data = []
    for tx in qifFile.get_transactions()[0]:
        date_str = tx.date.strftime('%Y-%m-%d') if tx.date else None

        data.append({
            'date': date_str,
            'amount': tx.amount,
            'memo': tx.memo,    
            'payee': tx.payee
            })
    

    df = pd.DataFrame(data)

    return df

def save_transactions_to_db(table, df, db_id, image_url=None):
    transactions = df.to_dict(orient='records')

    for tx in transactions:
        tx['amount'] = Decimal(str(tx['amount']))

    item = {
        'id': db_id,
        'transactions': transactions,
        'created_at': datetime.now(timezone.utc).isoformat()
    }

    response = table.put_item(Item=item, ConditionExpression="attribute_not_exists(id)")

    return response