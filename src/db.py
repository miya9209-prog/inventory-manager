import sqlite3
from datetime import datetime
import pandas as pd

class DB:
    def __init__(self, path="selleros_inventory.db"):
        self.path = path
        self.init()

    def conn(self):
        return sqlite3.connect(self.path)

    def init(self):
        with self.conn() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS products (
                product_no TEXT PRIMARY KEY, product_name TEXT, product_key TEXT, category TEXT, image_url TEXT,
                cafe24_display_status TEXT, cafe24_selling_status TEXT, product_soldout TEXT,
                supplier_name TEXT, lead_time_days INTEGER DEFAULT 5, safety_stock INTEGER DEFAULT 5, updated_at TEXT)""")
            con.execute("""CREATE TABLE IF NOT EXISTS inventory_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT, product_no TEXT, product_name TEXT, product_key TEXT, option_name TEXT, option_key TEXT,
                cafe24_stock INTEGER, cafe24_soldout_status TEXT, captured_at TEXT)""")
            con.execute("""CREATE TABLE IF NOT EXISTS sellmate_stock (
                product_no TEXT, product_name TEXT, product_key TEXT, purchase_name TEXT, option_name TEXT, option_key TEXT, supplier_name TEXT,
                sellmate_stock INTEGER, current_stock INTEGER, unshipped_qty INTEGER, sellmate_soldout TEXT, sellmate_selling TEXT,
                cost INTEGER, price INTEGER, updated_at TEXT)""")
            con.execute("""CREATE TABLE IF NOT EXISTS sales_daily (
                id INTEGER PRIMARY KEY AUTOINCREMENT, product_no TEXT, product_name TEXT, product_key TEXT, option_name TEXT, option_key TEXT,
                sales_date TEXT, order_qty INTEGER)""")
            con.execute("""CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, alert_type TEXT, product_no TEXT, product_name TEXT, severity TEXT, message TEXT, created_at TEXT)""")

    def df(self, sql, params=None):
        with self.conn() as con:
            return pd.read_sql_query(sql, con, params=params or [])

    def reset_all(self):
        with self.conn() as con:
            for t in ["products", "inventory_snapshots", "sellmate_stock", "sales_daily", "alerts"]:
                con.execute(f"DELETE FROM {t}")

    def replace_sellmate_stock(self, df):
        now = datetime.now().isoformat(timespec="seconds")
        with self.conn() as con:
            con.execute("DELETE FROM sellmate_stock")
            for _, r in df.iterrows():
                con.execute("""INSERT INTO sellmate_stock VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                    str(r.get("product_no", "")), r.get("product_name", ""), r.get("product_key", ""), r.get("purchase_name", ""),
                    r.get("option_name", ""), r.get("option_key", ""), r.get("supplier_name", ""), int(r.get("sellmate_stock", 0) or 0),
                    int(r.get("current_stock", 0) or 0), int(r.get("unshipped_qty", 0) or 0), r.get("sellmate_soldout", ""),
                    r.get("sellmate_selling", ""), int(r.get("cost", 0) or 0), int(r.get("price", 0) or 0), now))

    def upsert_products(self, rows):
        now = datetime.now().isoformat(timespec="seconds")
        with self.conn() as con:
            for r in rows:
                con.execute("""INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(product_no) DO UPDATE SET product_name=excluded.product_name, product_key=excluded.product_key,
                category=excluded.category, image_url=excluded.image_url, cafe24_display_status=excluded.cafe24_display_status,
                cafe24_selling_status=excluded.cafe24_selling_status, product_soldout=excluded.product_soldout,
                supplier_name=excluded.supplier_name, updated_at=excluded.updated_at""", (
                    str(r.get("product_no")), r.get("product_name", ""), r.get("product_key", ""), r.get("category", ""), r.get("image_url", ""),
                    r.get("display_status", ""), r.get("selling_status", ""), r.get("product_soldout", ""), r.get("supplier_name", ""),
                    int(r.get("lead_time_days", 5) or 5), int(r.get("safety_stock", 5) or 5), now))

    def insert_inventory_snapshots(self, rows):
        now = datetime.now().isoformat(timespec="seconds")
        with self.conn() as con:
            for r in rows:
                con.execute("""INSERT INTO inventory_snapshots (product_no,product_name,product_key,option_name,option_key,cafe24_stock,cafe24_soldout_status,captured_at)
                VALUES (?,?,?,?,?,?,?,?)""", (str(r.get("product_no", "")), r.get("product_name", ""), r.get("product_key", ""),
                    r.get("option_name", ""), r.get("option_key", ""), int(r.get("cafe24_stock", 0) or 0), r.get("soldout_status", ""), now))

    def insert_sales_daily(self, rows):
        if not rows: return
        with self.conn() as con:
            for r in rows:
                con.execute("INSERT INTO sales_daily (product_no,product_name,product_key,option_name,option_key,sales_date,order_qty) VALUES (?,?,?,?,?,?,?)",
                    (str(r.get("product_no", "")), r.get("product_name", ""), r.get("product_key", ""), r.get("option_name", ""), r.get("option_key", ""), r.get("sales_date"), int(r.get("order_qty", 0) or 0)))

    def replace_alerts(self, rows):
        now = datetime.now().isoformat(timespec="seconds")
        with self.conn() as con:
            con.execute("DELETE FROM alerts")
            for r in rows:
                con.execute("INSERT INTO alerts (alert_type,product_no,product_name,severity,message,created_at) VALUES (?,?,?,?,?,?)",
                    (r.get("alert_type", ""), str(r.get("product_no", "")), r.get("product_name", ""), r.get("severity", "info"), r.get("message", ""), now))
