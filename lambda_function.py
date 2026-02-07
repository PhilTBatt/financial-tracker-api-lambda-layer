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
    
    db_id = object_key.split("_", 1)[0]

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
    

    return pd.DataFrame(data)

def save_transactions_to_db(table, df: pd.DataFrame, metrics: dict, db_id: str):
    transactions = df.to_dict(orient='records')

    for tx in transactions:
        tx['amount'] = int(round(tx['amount'] * 100)) if tx['amount'] is not None else 0

    def pennies_array(arr):
        return [int(round(float(x) * 100)) for x in arr]

    def pennies_map_of_arrays(m):
        return {k: pennies_array(v) for k, v in m.items()}

    metrics_ddb = {
        "total_transactions": int(metrics["total_transactions"]),
        "date_range_label": metrics.get("date_range_label"),
        "monthly": {
            "labels": metrics["monthly"]["labels"],
            "in": pennies_array(metrics["monthly"]["in"]),
            "out": pennies_array(metrics["monthly"]["out"]),
            "avgOut": int(round(metrics["monthly"]["avgOut"] * 100)),
            "byCategoryOut": pennies_map_of_arrays(metrics["monthly"]["byCategoryOut"]),
        },
        "weekly": {
            "labels": metrics["weekly"]["labels"],
            "in": pennies_array(metrics["weekly"]["in"]),
            "out": pennies_array(metrics["weekly"]["out"]),
            "avgOut": int(round(metrics["weekly"]["avgOut"] * 100)),
            "byCategoryOut": pennies_map_of_arrays(metrics["weekly"]["byCategoryOut"]),
        },
        "buckets": metrics["buckets"]
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
    df = df.dropna(subset=["date"])

    if df.empty:
        return {
            "total_transactions": total_transactions,
            "date_range_label": None,
            "monthly": {"labels": [], "in": [], "out": [], "avgOut": 0.0, "byCategoryOut": {}},
            "weekly": {"labels": [], "in": [], "out": [], "avgOut": 0.0, "byCategoryOut": {}},
            "buckets": {"outgoingSize": {"labels": ["£0–5","£5–10","£10–25","£25–50","£50–100","£100–250","£250+"],
                                         "counts": [0,0,0,0,0,0,0]}}
        }

    start = df["date"].min()
    end = df["date"].max()
    date_range_label = f"{start.strftime('%b %Y')} – {end.strftime('%b %Y')}"

    out_df = df[df["amount"] < 0].copy()
    out_df["out"] = -out_df["amount"]
    out_df["category"] = out_df["description"].apply(categorise)

    in_df = df[df["amount"] > 0].copy()
    in_df["in"] = in_df["amount"]

    df["month"] = df["date"].dt.strftime("%Y-%m")

    month_labels = sorted(df["month"].unique().tolist())

    out_by_month = out_df.groupby(out_df["date"].dt.strftime("%Y-%m"))["out"].sum()
    in_by_month = in_df.groupby(in_df["date"].dt.strftime("%Y-%m"))["in"].sum()

    monthly_out = [float(out_by_month.get(m, 0.0)) for m in month_labels]
    monthly_in = [float(in_by_month.get(m, 0.0)) for m in month_labels]
    monthly_avg_out = float(sum(monthly_out) / len(monthly_out)) if month_labels else 0.0

    monthly_by_category_out = {}
    if not out_df.empty:
        out_df["month"] = out_df["date"].dt.strftime("%Y-%m")
        month_cat = out_df.groupby(["month", "category"])["out"].sum()
        categories = sorted(out_df["category"].dropna().unique().tolist())
        for cat in categories:
            monthly_by_category_out[cat] = [float(month_cat.get((m, cat), 0.0)) for m in month_labels]

    iso_all = df["date"].dt.isocalendar()
    df["iso_label"] = (
        iso_all["year"].astype(int).astype(str)
        + "-W"
        + iso_all["week"].astype(int).astype(str).str.zfill(2)
    )
    week_labels = sorted(df["iso_label"].unique().tolist())

    if not out_df.empty:
        iso_out = out_df["date"].dt.isocalendar()
        out_df["iso_label"] = (
            iso_out["year"].astype(int).astype(str)
            + "-W"
            + iso_out["week"].astype(int).astype(str).str.zfill(2)
        )
        out_by_week = out_df.groupby("iso_label")["out"].sum()
    else:
        out_by_week = {}

    if not in_df.empty:
        iso_in = in_df["date"].dt.isocalendar()
        in_df["iso_label"] = (
            iso_in["year"].astype(int).astype(str)
            + "-W"
            + iso_in["week"].astype(int).astype(str).str.zfill(2)
        )
        in_by_week = in_df.groupby("iso_label")["in"].sum()
    else:
        in_by_week = {}

    weekly_out = [float(out_by_week.get(w, 0.0)) for w in week_labels]
    weekly_in = [float(in_by_week.get(w, 0.0)) for w in week_labels]
    weekly_avg_out = float(sum(weekly_out) / len(weekly_out)) if week_labels else 0.0

    weekly_by_category_out = {}
    if not out_df.empty:
        week_cat = out_df.groupby(["iso_label", "category"])["out"].sum()
        categories = sorted(out_df["category"].dropna().unique().tolist())
        for cat in categories:
            weekly_by_category_out[cat] = [float(week_cat.get((w, cat), 0.0)) for w in week_labels]

    bucket_labels = ["£0–5", "£5–10", "£10–25", "£25–50", "£50–100", "£100–250", "£250–500", "£500+"]
    out_counts = [0] * len(bucket_labels)
    in_counts = [0] * len(bucket_labels)

    def bucket_idx(gbp: float) -> int:
        if gbp < 5: return 0
        if gbp < 10: return 1
        if gbp < 25: return 2
        if gbp < 50: return 3
        if gbp < 100: return 4
        if gbp < 250: return 5
        if gbp < 500: return 6
        return 7

    if not out_df.empty:
        for val in out_df["out"].dropna().tolist():
            out_counts[bucket_idx(float(val))] += 1

    if not in_df.empty:
        for val in in_df["in"].dropna().tolist():
            in_counts[bucket_idx(float(val))] += 1

    buckets = {
        "outgoingSize": {"labels": bucket_labels, "counts": out_counts},
        "incomingSize": {"labels": bucket_labels, "counts": in_counts},
    }

    return {
        "total_transactions": total_transactions,
        "date_range_label": date_range_label,
        "monthly": {
            "labels": month_labels,
            "in": monthly_in,
            "out": monthly_out,
            "avgOut": monthly_avg_out,
            "byCategoryOut": monthly_by_category_out
        },
        "weekly": {
            "labels": week_labels,
            "in": weekly_in,
            "out": weekly_out,
            "avgOut": weekly_avg_out,
            "byCategoryOut": weekly_by_category_out
        },
        "buckets": buckets
    }

def categorise(description: str) -> str:
    if not description:
        return "Other" 
    d = description.upper()

    if any(x in d for x in ["CASH WITHDRAWAL", "ATM"]):
        return "Cash"
    
    if any(x in d for x in ["BILL PAYMENT", "STANDING ORDER", "DIRECT DEBIT", "TRANSFER"]):
        return "Transfers"

    if any(x in d for x in ["TESCO", "ALDI", "LIDL", "ASDA", "SAINSBURY", "MORRISONS", "WOODLAND STORE"]):
        return "Groceries"

    if any(x in d for x in ["UBER", "TRAINLINE", "BUS", "ARRIVA", "FIRST", "TFL"]):
        return "Transport"

    if any(x in d for x in ["AMAZON", "AMZN", "EBAY"]):
        return "Online Shopping"

    if any(x in d for x in ["STEAM", "STEAMGAMES", "XBOX", "PLAYSTATION", "PSN", "XSOLLA", "NINTENDO", "GOOGLE PLAY", "GOOGLE YOUTUBE"]):
        return "Gaming"

    if any(x in d for x in ["WILLIAM HILL", "BET365", "LADBROKES", "CORAL", "SKY BET", "PADDY POWER"]):
        return "Gambling"
    
    if any(x in d for x in ["SNOOKER", "BOWL", "BOWLING", "WINTER GARDENS", "THEATRE", "CINEMA"]):
        return "Entertainment"

    return "Other"