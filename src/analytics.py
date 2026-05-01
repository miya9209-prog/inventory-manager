from datetime import date, timedelta
import pandas as pd
from src.db import now_iso
from src.season_rules import current_season_tags

def latest_inventory(db):
    return db.df("""
    SELECT i.* FROM inventory_snapshots i
    JOIN (
      SELECT product_no, option_name, MAX(captured_at) AS max_captured
      FROM inventory_snapshots GROUP BY product_no, option_name
    ) x ON i.product_no=x.product_no AND i.option_name=x.option_name AND i.captured_at=x.max_captured
    """)

def build_product_metrics(db):
    products = db.df("SELECT * FROM products")
    inv = latest_inventory(db)
    sales = db.df("SELECT * FROM sales_daily")
    if products.empty:
        return pd.DataFrame()
    if inv.empty:
        inv = pd.DataFrame(columns=["product_no","option_name","cafe24_stock","sellmate_stock","cafe24_soldout_status"])
    if sales.empty:
        sales = pd.DataFrame(columns=["product_no","option_name","sales_date","order_qty","shipped_qty","returned_qty"])

    today = date.today()
    rows = []
    for _, p in products.iterrows():
        pno = str(p.product_no)
        pi = inv[inv.product_no.astype(str) == pno]
        stock = int(pi["cafe24_stock"].fillna(0).sum()) if not pi.empty else 0
        sellmate_stock = int(pi["sellmate_stock"].fillna(0).sum()) if not pi.empty else None
        ps = sales[sales.product_no.astype(str) == pno].copy()
        if not ps.empty:
            ps["sales_date"] = pd.to_datetime(ps["sales_date"]).dt.date
            s3 = int(ps[ps.sales_date >= today - timedelta(days=2)]["order_qty"].sum())
            s7 = int(ps[ps.sales_date >= today - timedelta(days=6)]["order_qty"].sum())
            s14 = int(ps[ps.sales_date >= today - timedelta(days=13)]["order_qty"].sum())
            s30 = int(ps[ps.sales_date >= today - timedelta(days=29)]["order_qty"].sum())
        else:
            s3=s7=s14=s30=0
        avg_daily = max(s7 / 7, s14 / 14, 0)
        days_to_soldout = round(stock / avg_daily, 1) if avg_daily > 0 else None
        lead = int(p.get("lead_time_days", 3) or 3)
        safety = int(p.get("safety_stock", 5) or 5)
        reco = int(max((avg_daily * lead) + safety - stock, 0))
        rows.append({
            "product_no": pno,
            "상품명": p.product_name,
            "카테고리": p.category,
            "진열": p.cafe24_display_status,
            "판매": p.cafe24_selling_status,
            "품절": p.cafe24_soldout_status,
            "재고": stock,
            "물류재고": sellmate_stock,
            "3일판매": s3,
            "7일판매": s7,
            "14일판매": s14,
            "30일판매": s30,
            "일평균판매": round(avg_daily, 2),
            "예상품절일": days_to_soldout,
            "추천입고수량": reco,
            "시즌태그": p.season_tags or "",
            "리드타임": lead,
            "안전재고": safety,
        })
    return pd.DataFrame(rows)

def classify(metrics: pd.DataFrame):
    if metrics.empty:
        return metrics
    df = metrics.copy()
    def status(row):
        soldout = str(row.get("품절", "")).upper() in ["T", "Y", "TRUE", "SOLDOUT"] or row.get("재고",0) <= 0
        if soldout and row.get("7일판매",0) > 0:
            return "이미품절_인기"
        d = row.get("예상품절일")
        if d is not None and row.get("일평균판매",0) > 0:
            if d <= 1: return "긴급품절위험"
            if d <= 3: return "품절위험"
            if d <= 7: return "품절주의"
        if row.get("재고",0) >= 30 and row.get("30일판매",0) <= 3:
            return "악성재고후보"
        return "정상"
    df["상태"] = df.apply(status, axis=1)
    return df

def season_open_candidates(metrics: pd.DataFrame, month=None):
    if metrics.empty:
        return metrics
    tags = set(current_season_tags(month))
    def match(row):
        rowtags = set([x.strip() for x in str(row.get("시즌태그","")).split(",") if x.strip()])
        has_stock = row.get("재고",0) >= 10
        display_off = str(row.get("진열","")).upper() in ["F", "N", "FALSE", "DISPLAY_OFF", ""]
        low_sales = row.get("7일판매",0) <= 2
        return has_stock and bool(tags & rowtags) and (display_off or low_sales)
    return metrics[metrics.apply(match, axis=1)].copy()

def generate_alerts(metrics: pd.DataFrame, season_df: pd.DataFrame):
    alerts = []
    for _, r in metrics.iterrows():
        st = r.get("상태")
        if st in ["이미품절_인기", "긴급품절위험", "품절위험", "품절주의", "악성재고후보"]:
            severity = "high" if st in ["이미품절_인기", "긴급품절위험"] else "medium"
            if st == "악성재고후보": severity = "low"
            alerts.append({
                "alert_type": st,
                "product_no": r["product_no"],
                "option_name": "전체",
                "severity": severity,
                "message": f"{r['상품명']} / 재고 {r['재고']} / 7일판매 {r['7일판매']} / 예상품절 {r['예상품절일']}",
                "created_at": now_iso(),
            })
    for _, r in season_df.iterrows():
        alerts.append({
            "alert_type": "시즌오픈추천",
            "product_no": r["product_no"],
            "option_name": "전체",
            "severity": "medium",
            "message": f"{r['상품명']} / 현재 시즌 태그 {r['시즌태그']} / 재고 {r['재고']} / 진열 {r['진열']}",
            "created_at": now_iso(),
        })
    return alerts
