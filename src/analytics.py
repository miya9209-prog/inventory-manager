from datetime import date, timedelta
import math
import pandas as pd
from .utils import truthy_status, selling_on


def build_product_metrics(db):
    sm = db.df("SELECT * FROM sellmate_stock")
    products = db.df("SELECT * FROM products")
    inv = db.df("""SELECT product_no,product_name,product_key,option_name,option_key,cafe24_stock,cafe24_soldout_status FROM inventory_snapshots
                   WHERE id IN (SELECT MAX(id) FROM inventory_snapshots GROUP BY product_no, option_key)""")
    sales = db.df("SELECT product_no,product_key,sales_date,SUM(order_qty) order_qty FROM sales_daily GROUP BY product_no,product_key,sales_date")
    if sm.empty and products.empty: return pd.DataFrame()

    if sm.empty:
        base = products.copy(); base["sellmate_stock"] = pd.NA; base["current_stock"] = pd.NA; base["unshipped_qty"] = 0
    else:
        smp = sm.groupby(["product_key", "product_name"], as_index=False).agg({
            "sellmate_stock":"sum", "current_stock":"sum", "unshipped_qty":"sum", "cost":"max", "price":"max", "supplier_name":"first",
            "sellmate_soldout":"first", "sellmate_selling":"first"})
        if products.empty:
            base = smp.copy(); base["product_no"]=""; base["cafe24_display_status"]=""; base["cafe24_selling_status"]=""; base["product_soldout"]=""; base["lead_time_days"]=5; base["safety_stock"]=5
        else:
            base = products.merge(smp, on="product_key", how="outer", suffixes=("_cafe24", "_sm"))
            base["product_name"] = base["product_name_cafe24"].fillna(base["product_name_sm"])
            base["supplier_name"] = base.get("supplier_name_cafe24", pd.Series(dtype=str)).fillna(base.get("supplier_name_sm", ""))

    if not inv.empty:
        invs = inv.groupby("product_key", as_index=False).agg({"cafe24_stock":"sum", "cafe24_soldout_status":"max"})
        invs["카페24동기화"] = True
        base = base.merge(invs, on="product_key", how="left")
    else:
        base["cafe24_stock"] = pd.NA; base["cafe24_soldout_status"] = ""; base["카페24동기화"] = False
    base["카페24동기화"] = base.get("카페24동기화", False).fillna(False).astype(bool)

    today = date.today()
    for n in [3,7,14,30]:
        if sales.empty:
            sn = pd.DataFrame(columns=["product_key", f"{n}일판매"])
        else:
            start = today - timedelta(days=n-1)
            tmp=sales[pd.to_datetime(sales["sales_date"], errors="coerce").dt.date >= start]
            sn=tmp.groupby("product_key", as_index=False)["order_qty"].sum().rename(columns={"order_qty":f"{n}일판매"})
        base = base.merge(sn, on="product_key", how="left")

    for c in ["sellmate_stock","current_stock","unshipped_qty","cafe24_stock","3일판매","7일판매","14일판매","30일판매","lead_time_days","safety_stock"]:
        if c not in base: base[c]=0
        base[c]=pd.to_numeric(base[c], errors="coerce").fillna(0)

    base["기준재고"] = base["sellmate_stock"]
    base["일평균판매"] = base["7일판매"] / 7
    base["예상품절일"] = base.apply(lambda r: round(r["기준재고"] / r["일평균판매"], 1) if r["일평균판매"]>0 else None, axis=1)
    base["추천입고수량"] = ((base["일평균판매"] * base["lead_time_days"].replace(0,5)) + base["safety_stock"].replace(0,5) - base["기준재고"]).apply(lambda x: max(0, math.ceil(x)))

    rename = {"product_name":"상품명", "sellmate_stock":"셀메이트가용재고", "current_stock":"셀메이트현재재고", "unshipped_qty":"미발송주문수", "cafe24_stock":"카페24재고",
              "cafe24_display_status":"진열", "cafe24_selling_status":"판매", "product_soldout":"상품품절", "cafe24_soldout_status":"옵션품절", "supplier_name":"공급처"}
    base = base.rename(columns=rename)
    return classify(base)


def classify(df):
    if df.empty: return df
    df=df.copy(); df["상태"]="정상"; df["우선순위"]=3
    cafe_synced = df.get("카페24동기화", False)
    cafe_sold = cafe_synced & (df["옵션품절"].map(truthy_status) | df["상품품절"].map(truthy_status) | (df["카페24재고"] <= 0))
    sm_has = df["셀메이트가용재고"] > 0
    sm_zero = df["셀메이트가용재고"] <= 0
    selling = df["판매"].map(selling_on) | (df["판매"].astype(str).str.strip()=="")
    sold7 = df["7일판매"].fillna(0)
    days = pd.to_numeric(df["예상품절일"], errors="coerce")

    # 핵심: 실제재고가 있는데 카페24 품절/재고0이라 노출·구매가 막힌 상품
    m = sm_has & cafe_sold
    df.loc[m, ["상태","우선순위"]] = ["카페24품절_실제재고있음", 1]
    # 실제 재고가 없는데 판매중이면 주문 리스크
    m = cafe_synced & sm_zero & selling & ~cafe_sold
    df.loc[m, ["상태","우선순위"]] = ["실제재고없음_판매중위험", 1]
    # 곧 품절될 상품
    m = (df["상태"]=="정상") & (sold7 >= 3) & (days <= 3)
    df.loc[m, ["상태","우선순위"]] = ["긴급입고필요", 1]
    m = (df["상태"]=="정상") & (sold7 >= 2) & (days > 3) & (days <= 7)
    df.loc[m, ["상태","우선순위"]] = ["입고검토", 2]
    m = (df["상태"]=="정상") & (df["셀메이트가용재고"] >= 30) & (df["30일판매"] <= 2)
    df.loc[m, ["상태","우선순위"]] = ["악성재고후보", 4]
    return df.sort_values(["우선순위", "7일판매", "셀메이트가용재고"], ascending=[True, False, False])


def generate_alerts(metrics):
    rows=[]
    for _, r in metrics[metrics["우선순위"] <= 2].iterrows():
        rows.append({"alert_type": r["상태"], "product_no": r.get("product_no", ""), "product_name": r.get("상품명", ""),
                     "severity": "high" if r["우선순위"]==1 else "medium",
                     "message": f"{r.get('상품명','')} · {r['상태']} · 셀메이트 {int(r.get('셀메이트가용재고',0))} / 카페24 {int(r.get('카페24재고',0))} / 7일판매 {int(r.get('7일판매',0))}"})
    return rows
