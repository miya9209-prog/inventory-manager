from datetime import date, timedelta
import pandas as pd

def seed_sample_data(db):
    products = [
        {
            "product_no": "27930",
            "product_name": "클래식 랩스타일 조끼",
            "category": "조끼",
            "display_status": "T",
            "selling_status": "T",
            "season_tags": "봄,여름,조끼,레이어드",
            "lead_time_days": 3,
            "safety_stock": 5,
        },
        {
            "product_no": "30002",
            "product_name": "린넨 하프 집업 카라 니트",
            "category": "니트",
            "display_status": "T",
            "selling_status": "T",
            "season_tags": "봄,여름,린넨,니트",
            "lead_time_days": 3,
            "safety_stock": 5,
        },
        {
            "product_no": "27462",
            "product_name": "썸머 레이어드 네트 조끼",
            "category": "조끼",
            "display_status": "F",
            "selling_status": "T",
            "season_tags": "여름,조끼,레이어드,체형커버",
            "lead_time_days": 3,
            "safety_stock": 5,
        },
        {
            "product_no": "24835",
            "product_name": "사계절 실키 스트레치 셔츠",
            "category": "셔츠",
            "display_status": "T",
            "selling_status": "T",
            "season_tags": "봄,가을,셔츠,출근룩",
            "lead_time_days": 3,
            "safety_stock": 5,
        },
    ]

    db.upsert_products(products)

    db.insert_inventory_snapshots([
        {"product_no": "27930", "option_name": "", "cafe24_stock": 5, "soldout_status": "F"},
        {"product_no": "30002", "option_name": "", "cafe24_stock": 3, "soldout_status": "F"},
        {"product_no": "27462", "option_name": "아이보리", "cafe24_stock": 93, "soldout_status": "F"},
        {"product_no": "27462", "option_name": "베이지", "cafe24_stock": 54, "soldout_status": "F"},
        {"product_no": "27462", "option_name": "소라", "cafe24_stock": 89, "soldout_status": "F"},
        {"product_no": "27462", "option_name": "네이비", "cafe24_stock": 50, "soldout_status": "F"},
        {"product_no": "24835", "option_name": "스카이", "cafe24_stock": 1000, "soldout_status": "F"},
        {"product_no": "24835", "option_name": "애플민트", "cafe24_stock": 1000, "soldout_status": "F"},
        {"product_no": "24835", "option_name": "블랙", "cafe24_stock": 9999, "soldout_status": "F"},
    ])

    db.replace_sellmate_stock(pd.DataFrame([
        {"product_no": "27930", "product_name": "클래식 랩스타일 조끼", "option_name": "", "sellmate_stock": 0},
        {"product_no": "30002", "product_name": "린넨 하프 집업 카라 니트", "option_name": "", "sellmate_stock": 12},
        {"product_no": "27462", "product_name": "썸머 레이어드 네트 조끼", "option_name": "", "sellmate_stock": 286},
        {"product_no": "24835", "product_name": "사계절 실키 스트레치 셔츠", "option_name": "", "sellmate_stock": 20},
    ]))

    today = date.today()
    rows = []
    sales = {
        "27930": [4, 3, 2, 3, 4, 4, 3, 0, 0, 0, 0, 0, 0, 0],
        "30002": [5, 4, 3, 4, 4, 4, 4, 0, 0, 0, 0, 0, 0, 0],
        "27462": [1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        "24835": [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    }

    for product_no, arr in sales.items():
        for i, qty in enumerate(arr):
            rows.append({
                "product_no": product_no,
                "option_name": "",
                "sales_date": str(today - timedelta(days=i)),
                "order_qty": qty,
            })

    db.insert_sales_daily(rows)
