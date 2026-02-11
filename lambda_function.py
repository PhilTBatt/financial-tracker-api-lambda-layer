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
    
    first = object_key.split("_", 1)[0]
    db_id = first if "_" in object_key else str(uuid.uuid4())

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
    def pennies_val(x):
        return int(round(float(x) * 100))

    def pennies_map(m):
        return {k: pennies_val(v) for k, v in m.items()}

    def pennies_array(arr):
        return [int(round(float(x) * 100)) for x in arr]

    def pennies_map_of_arrays(m):
        return {k: pennies_array(v) for k, v in m.items()}
    
    transactions = df.to_dict(orient='records')

    for tx in transactions:
        tx['amount'] = int(round(tx['amount'] * 100)) if tx['amount'] is not None else 0

    metrics_ddb = {
        "totalTransactions": int(metrics.get("total_transactions", 0)),
        "dateRangeLabel": metrics.get("date_range_label"),
        "avgMonthlySpend": pennies_val(metrics.get("monthly", {}).get("avgOut", 0.0)),
        "avgWeeklySpend": pennies_val(metrics.get("weekly", {}).get("avgOut", 0.0)),
        "monthly": {
            "labels": metrics.get("monthly", {}).get("labels", []),
            "in": pennies_array(metrics.get("monthly", {}).get("in", [])),
            "out": pennies_array(metrics.get("monthly", {}).get("out", [])),
            "avgOut": pennies_val(metrics.get("monthly", {}).get("avgOut", 0.0)),
            "byCategoryOut": pennies_map_of_arrays(metrics.get("monthly", {}).get("byCategoryOut", {})),
        },
        "weekly": {
            "labels": metrics.get("weekly", {}).get("labels", []),
            "in": pennies_array(metrics.get("weekly", {}).get("in", [])),
            "out": pennies_array(metrics.get("weekly", {}).get("out", [])),
            "avgOut": pennies_val(metrics.get("weekly", {}).get("avgOut", 0.0)),
            "byCategoryOut": pennies_map_of_arrays(metrics.get("weekly", {}).get("byCategoryOut", {})),
        },

        "categories": {
            "outTotalByCategory": pennies_map(metrics.get("categories", {}).get("out_total_by_category", {})),
            "outCountByCategory": {
                k: int(v) for k, v in metrics.get("categories", {}).get("out_count_by_category", {}).items()
            },
            "avgOutByCategory": pennies_map(metrics.get("categories", {}).get("avg_out_by_category", {})),
            "outSizeBucketsByCategory": {
                "labels": metrics.get("categories", {}).get("out_size_buckets_by_category", {}).get("labels", []),
                "counts": {
                    k: [int(x) for x in arr]
                    for k, arr in metrics.get("categories", {}).get("out_size_buckets_by_category", {}).get("counts", {}).items()
                }
            }
        },
        "buckets": metrics.get("buckets", {"outgoingSize": {"labels": [], "counts": []}, "incomingSize": {"labels": [], "counts": []}}),
        "daily": {
            "labels": metrics.get("daily", {}).get("labels", []),
            "out": pennies_array(metrics.get("daily", {}).get("out", [])),
            "in": pennies_array(metrics.get("daily", {}).get("in", [])),
        },
        "rollingOut7d": {
            "window": int(metrics.get("rollingOut7d", {}).get("window", 7)),
            "values": pennies_array(metrics.get("rollingOut7d", {}).get("values", [])),
        },
        "topOutgoingTransactions": [
            {
                "date": t.get("date"),
                "amount": pennies_val(t.get("amount", 0.0)),
                "description": t.get("description"),
            }
            for t in (metrics.get("topOutgoingTransactions") or [])
        ]
    }

    item = {
        'id': db_id,
        'transactions': transactions,
        "metrics": metrics_ddb,
        'createdAt': datetime.now(timezone.utc).isoformat()
    }

    return table.put_item(Item=item, ConditionExpression="attribute_not_exists(id)")

def calculate_metrics(transactions: pd.DataFrame):
    df = transactions.copy()
    total_transactions = int(len(df))

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    bucket_labels = ["£0–5", "£5–10", "£10–25", "£25–50", "£50–100", "£100–250", "£250–500", "£500+"]
    out_counts = [0] * len(bucket_labels)
    in_counts = [0] * len(bucket_labels)

    if df.empty:
        return {
            "total_transactions": total_transactions,
            "date_range_label": None,
            "monthly": {"labels": [], "in": [], "out": [], "avgOut": 0.0, "byCategoryOut": {}},
            "weekly": {"labels": [], "in": [], "out": [], "avgOut": 0.0, "byCategoryOut": {}},
            "categories": {
                "out_total_by_category": {},
                "out_count_by_category": {},
                "avg_out_by_category": {},
                "out_size_buckets_by_category": {"labels": bucket_labels, "counts": {}}
            },
            "buckets": {
                "outgoingSize": {"labels": bucket_labels, "counts": out_counts},
                "incomingSize": {"labels": bucket_labels, "counts": in_counts}
            },
            "daily": {"labels": [], "out": [], "in": []},
            "rollingOut7d": {"window": 7, "values": []},
            "topOutgoingTransactions": []
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

    out_by_month = out_df.groupby(out_df["date"].dt.strftime("%Y-%m"))["out"].sum() if not out_df.empty else {}
    in_by_month = in_df.groupby(in_df["date"].dt.strftime("%Y-%m"))["in"].sum() if not out_df.empty else {}

    monthly_out = [float(out_by_month.get(m, 0.0)) for m in month_labels]
    monthly_in = [float(in_by_month.get(m, 0.0)) for m in month_labels]
    monthly_avg_out = float(sum(monthly_out) / len(monthly_out)) if month_labels else 0.0

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
    
    monthly_by_category_out = {}
    weekly_by_category_out = {}
    out_total_by_category = {}
    out_count_by_category = {}
    avg_out_by_category = {}
    out_size_buckets_by_category = {}

    if not out_df.empty:
        out_df["month"] = out_df["date"].dt.strftime("%Y-%m")
        month_cat = out_df.groupby(["month", "category"])["out"].sum()
        cats = sorted(out_df["category"].dropna().unique().tolist())
        for cat in cats:
            monthly_by_category_out[cat] = [float(month_cat.get((m, cat), 0.0)) for m in month_labels]

        week_cat = out_df.groupby(["iso_label", "category"])["out"].sum()
        for cat in cats:
            weekly_by_category_out[cat] = [float(week_cat.get((w, cat), 0.0)) for w in week_labels]

        cat_total = out_df.groupby("category")["out"].sum()
        cat_count = out_df.groupby("category")["out"].count()
        out_total_by_category = {cat: float(val) for cat, val in cat_total.items()}
        out_count_by_category = {cat: int(val) for cat, val in cat_count.items()}
        avg_out_by_category = {
            cat: float(out_total_by_category.get(cat, 0.0) / max(out_count_by_category.get(cat, 0), 1))
            for cat in out_total_by_category.keys()
        }

        for cat, grp in out_df.groupby("category"):
            counts = [0] * len(bucket_labels)
            for val in grp["out"].dropna().tolist():
                counts[bucket_idx(float(val))] += 1
            out_size_buckets_by_category[cat] = counts

        for val in out_df["out"].dropna().tolist():
            out_counts[bucket_idx(float(val))] += 1


    if not in_df.empty:
        for val in in_df["in"].dropna().tolist():
            in_counts[bucket_idx(float(val))] += 1

    buckets = {
        "outgoingSize": {"labels": bucket_labels, "counts": out_counts},
        "incomingSize": {"labels": bucket_labels, "counts": in_counts},
    }

    day_labels = pd.date_range(start.normalize(), end.normalize(), freq="D")
    day_label_strs = [d.strftime("%Y-%m-%d") for d in day_labels]

    out_by_day = out_df.groupby(out_df["date"].dt.strftime("%Y-%m-%d"))["out"].sum() if not out_df.empty else {}
    in_by_day = in_df.groupby(in_df["date"].dt.strftime("%Y-%m-%d"))["in"].sum() if not in_df.empty else {}

    daily_out = [float(out_by_day.get(day, 0.0)) for day in day_label_strs]
    daily_in = [float(in_by_day.get(day, 0.0)) for day in day_label_strs]

    roll = pd.Series(daily_out, dtype="float64").rolling(window=7, min_periods=1).mean().tolist()
    rolling_out_7d = [float(x) for x in roll]

    top_outgoing = []
    if not df.empty:
        out_only = df[df["amount"] < 0].copy()
        if not out_only.empty:
            out_only = out_only.sort_values("amount", ascending=True).head(10)
            top_outgoing = [
                {
                    "date": r["date"].strftime("%Y-%m-%d") if hasattr(r["date"], "strftime") else str(r["date"])[:10],
                    "amount": float(r["amount"]),
                    "description": None if pd.isna(r.get("description")) else str(r.get("description"))
                }
                for _, r in out_only.iterrows()
            ]

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
        "categories": {
            "out_total_by_category": out_total_by_category,
            "out_count_by_category": out_count_by_category,
            "avg_out_by_category": avg_out_by_category,
            "out_size_buckets_by_category": {
                "labels": bucket_labels,
                "counts": out_size_buckets_by_category
            }
        },
        "buckets": buckets,
        "daily": {
            "labels": day_label_strs,
            "out": daily_out,
            "in": daily_in
        },
        "rollingOut7d": {
            "window": 7,
            "values": rolling_out_7d
        },
        "topOutgoingTransactions": top_outgoing
    }

def categorise(description: str) -> str:
    if not description:
        return "Other" 
    
    d = description.upper()

    if any(x in d for x in ["CASH WITHDRAWAL", "ATM"]):
        return "Cash"

    if any(x in d for x in ["TESCO", "ALDI", "LIDL", "ASDA", "SAINSBURY", "Sainsbury", "MORRISONS", "WAITROSE", "MARKS", "M&S", "OCADO", "WOODLAND STORE", "CO-OP", "COOP", "CO OP", "SPAR", "PREMIER", "BUDGENS", "ICELAND", "FARMFOODS", "HERON", "COSTCUTTER", "NISA", "ONE STOP"]):
        return "Groceries"

    if any(x in d for x in ["UBER", "TRAINLINE", "ARRIVA", "FIRST BUS", "TFL", "NATIONAL RAIL", "LNER", "AVANTI", "NORTHERN", "TRANSPENNINE", "CROSSCOUNTRY", "GWR", "EMR", "SWR", "TPE", "METROLINK", "TRAM", "STAGECOACH", "COACH", "NATIONAL EXPRESS", "MEGABUS", "SHELL", "ESSO", "TEXACO", "PETROL", "FUEL", "GARAGE", "SERVICE STATION", "PARKING", "CAR PARK", "RINGGO", "NCP", "APCOA"]):
        return "Transport"

    if any(x in d for x in ["AMAZON", "AMZN", "EBAY", "PAYPAL", "PP*", "PAYPAL *", "ETSY", "ALIEXPRESS", "TEMU", "SHEIN", "SHOPIFY", "STRIPE", "SQ *", "SQUARE", "GUMTREE", "VINTED", "DEPOP", "PANDORA", "HUEL"]):
        return "Online Shopping"
    
    if any(x in d for x in ["NETFLIX", "SPOTIFY", "DISNEY", "AMAZON PRIME", "PRIME VIDEO", "APPLE.COM/BILL", "APPLE MUSIC", "ICLOUD", "GOOGLE ONE", "MICROSOFT", "ADOBE", "NOW TV", "NOWTV", "SKY", "BT SPORT", "BT*", "AUDIBLE", "KINDLE UNLTD", "KINDLE UNLIMITED", "PATREON", "DATACAMP"]):
        return "Subscriptions"

    if any(x in d for x in ["STEAM", "STEAMGAMES", "XBOX", "MICROSOFT*XBOX", "MICROSOFT XBOX", "XBOXLIVE", "PLAYSTATION", "SONY", "SIE", "PSN", "NINTENDO", "NINTENDO ESHOP", "E-SHOP", "EPIC GAMES", "EPICGAMES", "RIOT GAMES", "BLIZZARD", "BATTLE.NET", "JAGEX", "RUNESCAPE", "GOOGLE PLAY", "GOOGLE*PLAY", "APPLE.COM/BILL", "XSOLLA", "GAMIVO", "ENEBA", "KINGUIN"]):
        return "Gaming"

    if any(x in d for x in ["WILLIAM HILL", "WILLIAMHILL", "BET365", "LADBROKES", "CORAL", "SKY BET", "SKYBET", "PADDY POWER", "PADDYPOWER", "BETFAIR", "BETFAIR EXCHANGE", "UNIBET", "888", "888SPORT", "888CASINO", "TOMBOLA", "MECCA", "GALA", "GROSVENOR", "LOTTERY", "NATIONAL LOTTERY", "LOTTO", "CASINO", "BOOKMAKER", "BOOKIES"]):
        return "Gambling"
    
    if any(x in d for x in ["SNOOKER", "BOWL", "BOWLING", "THEATRE", "CINEMA", "ODEON", "VUE", "CINEWORLD", "WINTER GARDENS", "TICKETMASTER", "SEE TICKETS", "DICE", "EVENTBRITE", "GIG", "CONCERT", "FESTIVAL", "GYM", "LEISURE", "SWIMMING", "POOL"]):
        return "Entertainment"
    
    if any(x in d for x in ["CAFE", "CAFÉ", "COFFEE", "STARBUCKS", "COSTA", "PRET", "NERO", "GREGGS", "WETHERSPOON", "SPOONS", "MARSTON", "GREENE KING", "MCDONALD", "KFC", "BURGER", "SUBWAY", "DOMINO", "PIZZA", "PAPA JOHN", "PIZZA HUT", "TAKEAWAY", "CHIPPY", "GRILL", "KEBAB", "RESTAURANT", "BISTRO", "PUB", "INN", "TAVERN", "BAR", "DELIVEROO", "JUST EAT", "UBER EATS"]):
        return "Food/Drink"
    
    if any(x in d for x in ["BILL PAYMENT", "STANDING ORDER", "DIRECT DEBIT", "TRANSFER", "FASTER PAYMENT", "BACS", "CHAPS", "BANK GIRO", "GIRO", "INTERNAL TRANSFER", "PAYMENT REF", "REF:", "RENT", "LETTING", "ESTATE", "HOUSING", "PROPERTY", "LANDLORD"]):
        return "Transfers"

    return "Other"