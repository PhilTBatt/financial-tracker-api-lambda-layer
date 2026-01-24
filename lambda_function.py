import os
import io
import logging
import boto3
import uuid
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
    
    db_id = str(uuid.uuid4())

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
        metrics = calculate_metrics(df)
        logger.info(f"Calculating metrics for transactions.")
    except Exception as e:
        logger.error(f"Error calculating metrics: {str(e)}")
        raise

    try:
        save_transactions_to_db(table, df, metrics, db_id)
        logger.info(f"DF saved to DB with ID: {db_id}.")
    except Exception as e:
        logger.error(f"Error saving infomation to database: {str(e)}")
        raise

    return {
        'statusCode': 200,
        'msg': 'Lamdba function successful'}

def process_file(qifFile):
    data = []
    for tx in qifFile.get_transactions()[0]:
        date_str = tx.date.strftime('%Y-%m-%d') if tx.date else None

        data.append({
            'date': date_str,
            'amount': tx.amount,
            'description': tx.payee
            })
    

    df = pd.DataFrame(data)

    return df

def save_transactions_to_db(table, df: pd.DataFrame, metrics: dict, db_id: str):
    transactions = df.to_dict(orient='records')

    for tx in transactions:
        tx['amount'] = Decimal(str(tx['amount']))

    metrics_ddb = {
        "total_transactions": int(metrics["total_transactions"]),
        "total_spent": Decimal(str(metrics["total_spent"])),
        "avg_monthly_spend": Decimal(str(metrics["avg_monthly_spend"])),
        "top_category": metrics["top_category"],
        "top_category_spent": Decimal(str(metrics["top_category_spent"])),
        "date_range_label": metrics["date_range_label"],
        "monthly_spend_history": [
            { "period": p["period"], "amount": Decimal(str(p["amount"])) }    for p in metrics["monthly_spend_history"]
        ]
    }


    item = {
        'id': db_id,
        'transactions': transactions,
        "metrics": metrics_ddb,
        'created_at': datetime.now(timezone.utc).isoformat()
    }

    response = table.put_item(Item=item, ConditionExpression="attribute_not_exists(id)")

    return response

def calculate_metrics(transactions: pd.DataFrame):
    df = transactions.copy()

    total_transactions = int(len(df))

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    spend_df = df[df["amount"] < 0].copy()
    spend_df["spend"] = -spend_df["amount"]

    total_spent = float(spend_df["spend"].sum())

    valid_dates = df["date"].dropna()
    if len(valid_dates) > 0:
        start = valid_dates.min()
        end = valid_dates.max()
        date_range_label = f"{start.strftime('%b %Y')} – {end.strftime('%b %Y')}"
        months_in_range = (end.year - start.year) * 12 + (end.month - start.month) + 1

    else:
        date_range_label = None
        months_in_range = 0

    avg_monthly_spend = float(total_spent / months_in_range) if months_in_range > 0 else 0.0


    if len(spend_df) > 0:
        spend_df["period"] = spend_df["date"].dt.strftime("%Y-%m")
        monthly = spend_df.groupby("period")["spend"].sum().sort_index()
        monthly_spend_history = [{"period": p, "amount": float(a)} for p, a in monthly.items()]
    else:
        monthly_spend_history = []

    spend_df["category"] = spend_df["description"].apply(categorise)
    by_cat = spend_df.groupby("category")["spend"].sum()

    top_category = by_cat.idxmax() if len(by_cat) else None
    top_category_spent = float(by_cat.max()) if len(by_cat) else 0.0

    metrics = {
        "total_transactions": total_transactions,
        "total_spent": total_spent,
        "avg_monthly_spend": avg_monthly_spend,
        "top_category": top_category,
        "top_category_spent": top_category_spent,
        "date_range_label": date_range_label,
        "monthly_spend_history": monthly_spend_history
    }

    return metrics

def categorise(description: str) -> str:
    if not description:
        return "Other" 
    d = description.upper()

    if any(x in d for x in ["CASH WITHDRAWAL", "ATM"]):
        return "Cash"
    
    if any(x in d for x in ["BILL PAYMENT", "STANDING ORDER", "DIRECT DEBIT", "TRANSFER"]):
        return "Bills / Transfers"

    if any(x in d for x in ["TESCO", "ALDI", "LIDL", "ASDA", "SAINSBURY", "MORRISONS", "WOODLAND STORE"]):
        return "Shopping"

    if any(x in d for x in ["UBER", "TRAINLINE", "BUS", "ARRIVA", "FIRST", "TFL"]):
        return "Transport"

    if any(x in d for x in ["AMAZON", "AMZN", "EBAY"]):
        return "Online shopping"

    if any(x in d for x in ["STEAM", "STEAMGAMES", "XBOX", "PLAYSTATION", "PSN", "XSOLLA", "NINTENDO", "GOOGLE PLAY", "GOOGLE YOUTUBE"]):
        return "Gaming"

    if any(x in d for x in ["WILLIAM HILL", "BET365", "LADBROKES", "CORAL", "SKY BET", "PADDY POWER"]):
        return "Gambling"
    
    if any(x in d for x in ["SNOOKER", "BOWL", "BOWLING", "WINTER GARDENS", "THEATRE", "CINEMA"]):
        return "Entertainment"

    return "Other"