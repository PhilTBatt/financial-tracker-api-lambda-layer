import os
import io
import logging
import boto3
import pandas as pd
import matplotlib.pyplot as plt
import uuid
from datetime import datetime
from decimal import Decimal
from qifparse.parser import QifParser

os.environ['MPLCONFIGDIR'] = '/tmp/matplotlib'

s3 = boto3.client('s3')

logger = logging.getLogger()
logger.setLevel("INFO")

def lambda_handler(event, context):
    try:
        record = event['Records'][0]
        bucket_name = record['s3']['bucket']['name']
        object_key = record['s3']['object']['key']

        logger.info(f"File uploaded: {object_key} in bucket: {bucket_name}")

        response = s3.get_object(Bucket=bucket_name, Key=object_key)
        file_contents = response['Body'].read().decode('utf-8')
        qif = QifParser.parse(io.StringIO(file_contents))

        data = []
        for tx in qif.get_transactions()[0]:
            date_str = tx.date.strftime('%Y-%m-%d') if tx.date else None
            
            data.append({
                'date': date_str,
                'amount': tx.amount,
                'memo': tx.memo,    
                'payee': tx.payee
            })

        df = pd.DataFrame(data)

        if df.empty:
            logger.error("No transactions found in QIF file.")
            return
        
        logger.info(f"File parsed successfully with {len(df)} transactions.")

    except Exception as e:
        logger.error(f"Error processing order: {str(e)}")
        raise