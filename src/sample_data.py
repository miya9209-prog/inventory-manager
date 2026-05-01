from datetime import date, timedelta
from src.db import now_iso
from src.season_rules import infer_tags

PRODUCTS = [
    ("27930", "클래식 랩스타일 조끼", "조끼", 5, "T", "T", "F"),
    ("27462", "썸머 레이어드 네트 조끼", "조끼", 47, "F", "T", "F"),
    ("27434", "올가 S 507 블랙 코튼 팬츠", "팬츠", 12, "T", "T", "F"),
    ("24835", "사계절 실키 스트레치 셔츠", "셔츠", 82, "T", "T", "F"),
    ("26679", "F. 모리 절개 티셔츠", "티셔츠", 33, "T", "T", "F"),
    ("30001", "무드 시어서커 이지 핏 점퍼", "점퍼", 64, "F", "T", "F"),
    ("30002", "린넨 하프 집업 카라 니트", "니트", 3, "T", "T", "F"),
    ("30003", "컬러 배색 쿨메쉬 긴팔 가디건", "가디건", 6, "T", "T", "F"),
]

def seed(db):
    products = []
    inv = []
    today = date.today()
    for no, name, cat, stock, display, selling, soldout in PRODUCTS:
        products.append({
            "product_no": no, "product_name": name, "category": cat,
            "image_url": "", "cafe24_display_status": display,
            "cafe24_selling_status": selling, "cafe24_soldout_status": soldout,
            "season_tags": infer_tags(name, cat), "supplier_name": "", "lead_time_days": 3,
            "safety_stock": 5, "updated_at": now_iso()
        })
        inv.append({"product_no": no, "option_name": "기본", "cafe24_stock": stock, "sellmate_stock": stock, "cafe24_soldout_status": soldout, "captured_at": now_iso()})
    db.upsert_products(products)
    db.insert_inventory_snapshots(inv)
    sales = []
    pattern = {
        "27930": [2,3,4,5,3,4,2],
        "27462": [0,0,1,0,1,0,0],
        "27434": [1,1,2,2,2,1,1],
        "24835": [0,0,0,0,1,0,0],
        "26679": [1,0,1,0,0,1,0],
        "30001": [0,0,0,0,0,0,0],
        "30002": [3,4,4,5,3,4,5],
        "30003": [1,2,2,1,3,2,2],
    }
    for product_no, vals in pattern.items():
        for i, qty in enumerate(vals):
            d = today - timedelta(days=6-i)
            sales.append({"product_no": product_no, "option_name": "기본", "sales_date": d.isoformat(), "order_qty": qty, "shipped_qty": max(qty-1,0), "returned_qty": 0})
    db.upsert_sales_daily(sales)
