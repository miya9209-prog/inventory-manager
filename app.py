import math
from datetime import date, timedelta
import pandas as pd

CURRENT_MONTH_TAGS = {
    1: ["겨울", "니트", "아우터"],
    2: ["겨울", "봄", "간절기"],
    3: ["봄", "간절기", "자켓", "셔츠"],
    4: ["봄", "가정의달", "모임룩", "셔츠", "조끼"],
    5: ["여름", "가정의달", "모임룩", "린넨", "조끼", "니트"],
    6: ["여름", "린넨", "시어서커", "살안타템", "냉감"],
    7: ["여름", "휴가룩", "장마", "쿨링", "원피스"],
    8: ["여름", "휴가룩", "초가을"],
    9: ["가을", "간절기", "자켓", "셔츠"],
    10: ["가을", "니트", "자켓", "모임룩"],
    11: ["겨울", "니트", "아우터"],
    12: ["겨울", "연말모임", "아우터"],
}

def build_product_metrics(db):
    products = db.df("SELECT * FROM products")
    sm_raw = db.df("""
        SELECT product_no, product_name, SUM(sellmate_stock) AS sellmate_stock
        FROM sellmate_stock
        GROUP BY product_no, product_name
    """)

    if products.empty and not sm_raw.empty:
        products = sm_raw[["product_no", "product_name"]].copy()
        products["category"] = ""
        products["image_url"] = ""
        products["cafe24_display_status"] = "T"
        products["cafe24_selling_status"] = "T"
        products["season_tags"] = ""
        products["supplier_name"] = ""
        products["lead_time_days"] = 3
        products["safety_stock"] = 5

    if products.empty:
        return pd.DataFrame()

    inv = db.df("""
        SELECT product_no, option_name, cafe24_stock, cafe24_soldout_status
        FROM inventory_snapshots
        WHERE id IN (
            SELECT MAX(id)
            FROM inventory_snapshots
            GROUP BY product_no, option_name
        )
    """)

    sales = db.df("""
        SELECT product_no, sales_date, SUM(order_qty) AS order_qty
        FROM sales_daily
        GROUP BY product_no, sales_date
    """)

    df = products.rename(columns={
        "product_name": "상품명",
        "category": "카테고리",
        "cafe24_display_status": "진열",
        "cafe24_selling_status": "판매",
        "season_tags": "시즌태그",
    })

    if inv.empty:
        inv = pd.DataFrame(columns=["product_no", "cafe24_stock", "cafe24_soldout_status"])

    inv_sum = inv.groupby("product_no", as_index=False).agg({
        "cafe24_stock": "sum",
        "cafe24_soldout_status": "max",
    }).rename(columns={
        "cafe24_stock": "카페24재고",
        "cafe24_soldout_status": "품절",
    })

    sm_by_no = sm_raw.groupby("product_no", as_index=False)["sellmate_stock"].sum().rename(columns={
        "sellmate_stock": "셀메이트재고"
    })

    sm_by_name = sm_raw.groupby("product_name", as_index=False)["sellmate_stock"].sum().rename(columns={
        "product_name": "상품명",
        "sellmate_stock": "셀메이트재고_상품명매칭",
    })

    df = df.merge(inv_sum, on="product_no", how="left")
    df = df.merge(sm_by_no, on="product_no", how="left")
    df = df.merge(sm_by_name, on="상품명", how="left")
    df["셀메이트재고"] = df["셀메이트재고"].fillna(df["셀메이트재고_상품명매칭"])
    df = df.drop(columns=["셀메이트재고_상품명매칭"], errors="ignore")

    today = date.today()

    def sales_n(n):
        if sales.empty:
            return pd.DataFrame(columns=["product_no", f"{n}일판매"])
        start = today - timedelta(days=n - 1)
        s = sales[pd.to_datetime(sales["sales_date"]).dt.date >= start]
        return s.groupby("product_no", as_index=False)["order_qty"].sum().rename(columns={"order_qty": f"{n}일판매"})

    for n in [3, 7, 14, 30]:
        df = df.merge(sales_n(n), on="product_no", how="left")

    for col in ["카페24재고", "셀메이트재고", "3일판매", "7일판매", "14일판매", "30일판매"]:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["기준재고"] = df["셀메이트재고"]
    df.loc[df["셀메이트재고"].isna(), "기준재고"] = df.loc[df["셀메이트재고"].isna(), "카페24재고"]
    df["기준재고"] = df["기준재고"].fillna(0)

    avg_daily = df["7일판매"] / 7

    df["예상품절일"] = df.apply(
        lambda r: round(r["기준재고"] / (r["7일판매"] / 7), 1) if r["7일판매"] > 0 else None,
        axis=1
    )

    df["추천입고수량"] = (
        (avg_daily * df["lead_time_days"].fillna(3))
        + df["safety_stock"].fillna(5)
        - df["기준재고"]
    ).apply(lambda x: max(0, math.ceil(x)))

    return df

def _is_truthy_series(s):
    return s.astype(str).str.upper().isin(["T", "Y", "TRUE", "1", "품절"])

def classify_metrics(df):
    if df.empty:
        return df

    df = df.copy()
    df["상태"] = "정상"

    cafe_soldout = _is_truthy_series(df["품절"])
    cafe_stock_zero = df["카페24재고"].fillna(0) <= 0
    sm_stock_zero = df["셀메이트재고"].fillna(0) <= 0
    selling_on = df["판매"].astype(str).str.upper().isin(["T", "Y", "TRUE", "1", "판매중"])

    df.loc[(sm_stock_zero) & (df["7일판매"] >= 5), "상태"] = "실제재고품절_인기"
    df.loc[(cafe_soldout) & (df["7일판매"] >= 5), "상태"] = "카페24품절처리_인기"
    df.loc[(cafe_stock_zero | cafe_soldout) & (df["셀메이트재고"] > 0), "상태"] = "카페24품절_실제재고있음"
    df.loc[(sm_stock_zero) & (selling_on) & (~cafe_soldout), "상태"] = "실제재고없음_판매중위험"

    days = pd.to_numeric(df["예상품절일"], errors="coerce")
    df.loc[(df["상태"] == "정상") & (days <= 1), "상태"] = "긴급품절위험"
    df.loc[(df["상태"] == "정상") & (days > 1) & (days <= 3), "상태"] = "품절위험"
    df.loc[(df["상태"] == "정상") & (days > 3) & (days <= 7), "상태"] = "품절주의"
    df.loc[(df["상태"] == "정상") & (df["기준재고"] >= 30) & (df["30일판매"] <= 3), "상태"] = "악성재고후보"

    return df

def season_open_candidates(df):
    if df.empty:
        return df

    tags = CURRENT_MONTH_TAGS.get(date.today().month, [])
    pattern = "|".join(tags)

    if not pattern:
        return df.iloc[0:0]

    has_season = df["시즌태그"].fillna("").str.contains(pattern, case=False, regex=True)
    weak_exposure = (df["진열"].astype(str).str.upper() != "T") | (df["7일판매"] <= 2)
    enough_stock = df["기준재고"] >= 10

    return df[has_season & weak_exposure & enough_stock].copy()

def generate_alerts(metrics, season_df):
    rows = []

    if metrics.empty:
        return rows

    urgent_states = [
        "실제재고품절_인기",
        "카페24품절처리_인기",
        "카페24품절_실제재고있음",
        "실제재고없음_판매중위험",
        "긴급품절위험",
        "품절위험",
    ]

    for _, r in metrics[metrics["상태"].isin(urgent_states)].iterrows():
        rows.append({
            "alert_type": r["상태"],
            "product_no": r["product_no"],
            "severity": "high",
            "message": f"{r['상품명']} · 상태 {r['상태']} · 셀메이트재고 {r['셀메이트재고']} / 카페24재고 {r['카페24재고']}",
        })

    for _, r in season_df.iterrows():
        rows.append({
            "alert_type": "시즌오픈추천",
            "product_no": r["product_no"],
            "severity": "medium",
            "message": f"{r['상품명']} · 시즌태그 {r['시즌태그']} · 실제재고 {r['기준재고']}",
        })

    return rows
