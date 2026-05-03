import sqlite3
from datetime import datetime
import pandas as pd

class DB:
    def __init__(self, path):
        self.path = path
        self.init()

    def conn(self):
        return sqlite3.connect(self.path)

    def init(self):
        with self.conn() as con:
            con.execute("""
            CREATE TABLE IF NOT EXISTS products (
                product_no TEXT PRIMARY KEY,
                product_name TEXT,
                category TEXT,
                image_url TEXT,
                cafe24_display_status TEXT,
                cafe24_selling_status TEXT,
                season_tags TEXT,
                supplier_name TEXT,
                lead_time_days INTEGER DEFAULT 3,
                safety_stock INTEGER DEFAULT 5,
                updated_at TEXT
            )
            """)
            con.execute("""
            CREATE TABLE IF NOT EXISTS inventory_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_no TEXT,
                option_name TEXT,
                cafe24_stock INTEGER,
                cafe24_soldout_status TEXT,
                captured_at TEXT
            )
            """)
            con.execute("""
            CREATE TABLE IF NOT EXISTS sellmate_stock (
                product_no TEXT,
                product_name TEXT,
                option_name TEXT,
                sellmate_stock INTEGER,
                updated_at TEXT
            )
            """)
            con.execute("""
            CREATE TABLE IF NOT EXISTS sales_daily (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_no TEXT,
                option_name TEXT,
                sales_date TEXT,
                order_qty INTEGER,
                shipped_qty INTEGER DEFAULT 0,
                returned_qty INTEGER DEFAULT 0
            )
            """)
            con.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT,
                product_no TEXT,
                option_name TEXT,
                severity TEXT,
                message TEXT,
                status TEXT DEFAULT 'open',
                created_at TEXT,
                resolved_at TEXT
            )
            """)

    def df(self, sql, params=None):
        with self.conn() as con:
            return pd.read_sql_query(sql, con, params=params or [])

    def reset_all(self):
        with self.conn() as con:
            for table in ["products", "inventory_snapshots", "sellmate_stock", "sales_daily", "alerts"]:
                con.execute(f"DELETE FROM {table}")

    def upsert_products(self, rows):
        now = datetime.now().isoformat(timespec="seconds")
        with self.conn() as con:
            for r in rows:
                con.execute("""
                INSERT INTO products (
                    product_no, product_name, category, image_url,
                    cafe24_display_status, cafe24_selling_status, season_tags,
                    supplier_name, lead_time_days, safety_stock, updated_at
                )
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(product_no) DO UPDATE SET
                    product_name=excluded.product_name,
                    category=excluded.category,
                    image_url=excluded.image_url,
                    cafe24_display_status=excluded.cafe24_display_status,
                    cafe24_selling_status=excluded.cafe24_selling_status,
                    supplier_name=excluded.supplier_name,
                    lead_time_days=excluded.lead_time_days,
                    safety_stock=excluded.safety_stock,
                    updated_at=excluded.updated_at
                """, (
                    str(r.get("product_no")),
                    r.get("product_name", ""),
                    r.get("category", ""),
                    r.get("image_url", ""),
                    r.get("display_status", "T"),
                    r.get("selling_status", "T"),
                    r.get("season_tags", ""),
                    r.get("supplier_name", ""),
                    int(r.get("lead_time_days", 3) or 3),
                    int(r.get("safety_stock", 5) or 5),
                    now,
                ))

    def insert_inventory_snapshots(self, rows):
        now = datetime.now().isoformat(timespec="seconds")
        with self.conn() as con:
            for r in rows:
                con.execute("""
                INSERT INTO inventory_snapshots (
                    product_no, option_name, cafe24_stock, cafe24_soldout_status, captured_at
                )
                VALUES (?,?,?,?,?)
                """, (
                    str(r.get("product_no")),
                    r.get("option_name", ""),
                    int(r.get("cafe24_stock", 0) or 0),
                    r.get("soldout_status", "F"),
                    now,
                ))

    def replace_sellmate_stock(self, df):
        now = datetime.now().isoformat(timespec="seconds")
        required = ["product_no", "product_name", "option_name", "sellmate_stock"]
        for c in required:
            if c not in df.columns:
                raise ValueError(f"필수 컬럼 누락: {c}")

        with self.conn() as con:
            con.execute("DELETE FROM sellmate_stock")
            for _, r in df.iterrows():
                con.execute("""
                INSERT INTO sellmate_stock (
                    product_no, product_name, option_name, sellmate_stock, updated_at
                )
                VALUES (?,?,?,?,?)
                """, (
                    str(r.get("product_no")),
                    r.get("product_name", ""),
                    r.get("option_name", ""),
                    int(r.get("sellmate_stock", 0) or 0),
                    now,
                ))

    def insert_sales_daily(self, rows):
        with self.conn() as con:
            for r in rows:
                con.execute("""
                INSERT INTO sales_daily (
                    product_no, option_name, sales_date, order_qty, shipped_qty, returned_qty
                )
                VALUES (?,?,?,?,?,?)
                """, (
                    str(r.get("product_no")),
                    r.get("option_name", ""),
                    r.get("sales_date"),
                    int(r.get("order_qty", 0) or 0),
                    int(r.get("shipped_qty", 0) or 0),
                    int(r.get("returned_qty", 0) or 0),
                ))

    def replace_alerts(self, rows):
        now = datetime.now().isoformat(timespec="seconds")
        with self.conn() as con:
            con.execute("DELETE FROM alerts")
            for r in rows:
                con.execute("""
                INSERT INTO alerts (
                    alert_type, product_no, option_name, severity, message, status, created_at
                )
                VALUES (?,?,?,?,?,?,?)
                """, (
                    r.get("alert_type", ""),
                    str(r.get("product_no")),
                    r.get("option_name", ""),
                    r.get("severity", "info"),
                    r.get("message", ""),
                    "open",
                    now,
                ))
