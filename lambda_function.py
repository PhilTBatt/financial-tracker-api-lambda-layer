import boto3
import io
import pandas as pd
import matplotlib.pyplot as plt
import uuid
from datetime import datetime

from decimal import Decimal
from qifparse.parser import QifParser

def lambda_handler(event, context):
    record = event['Records'][0]
    bucket_name = record['s3']['bucket']['name']
    object_key = record['s3']['object']['key']

    print(f"File uploaded: {object_key} in bucket: {bucket_name}")

    s3 = boto3.client('s3')
    response = s3.get_object(Bucket=bucket_name, Key=object_key)
    file_contents = response['Body'].read().decode('utf-8')
    qif = QifParser.parse(io.StringIO(file_contents)) 

    data = []
    for tx in qif.get_transactions():
        data.append({
            'date': tx.date.strftime('%Y-%m-%d'),
            'amount': tx.amount,
            'memo': tx.memo,    
            'payee': tx.payee
        })

    df = pd.DataFrame(data)

    if df.empty:
        print("No transactions found in QIF file.")
        return

    image_key = f'output/images/{uuid.uuid4()}.png'
    image_url = plot_image(s3, bucket_name, image_key, df)

    save_full_batch(boto3.resource('dynamodb').Table('financial-app-db'), df, image_url)

    print(f"Saved parsed transactions from '{object_key}' to DynamoDB.")

def plot_image(s3, bucket, s3_key, data):
    fig, ax = plt.subplots()
    ax.plot([1, 2, 3], [100, 200, 300])
    plt.title("Transaction Chart")

    buffer = io.BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)

    s3.put_object(Bucket=bucket, Key=s3_key, Body=buffer, ContentType='image/png')
    url = f'https://{bucket}.s3.amazonaws.com/{s3_key}'
    return url


def save_full_batch(table, df, image_url=None):
    transactions = df.to_dict(orient='records')

    for tx in transactions:
        tx['amount'] = Decimal(str(tx['amount']))

    item = {
        'id': str(uuid.uuid4()),
        'transactions': transactions,
        'created_at': datetime.utcnow().isoformat()
    }

    if image_url:
        item['image_url'] = image_url

    table.put_item(Item=item)