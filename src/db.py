import sqlite3
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
  product_no TEXT PRIMARY KEY,
  product_name TEXT,
  category TEXT,
  image_url TEXT,
  cafe24_display_status TEXT,
  cafe24_selling_status TEXT,
  cafe24_soldout_status TEXT,
  season_tags TEXT,
  supplier_name TEXT,
  lead_time_days INTEGER DEFAULT 3,
  safety_stock INTEGER DEFAULT 5,
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS inventory_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  product_no TEXT,
  option_name TEXT,
  cafe24_stock INTEGER,
  sellmate_stock INTEGER,
  cafe24_soldout_status TEXT,
  captured_at TEXT
);
CREATE TABLE IF NOT EXISTS sales_daily (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  product_no TEXT,
  option_name TEXT,
  sales_date TEXT,
  order_qty INTEGER DEFAULT 0,
  shipped_qty INTEGER DEFAULT 0,
  returned_qty INTEGER DEFAULT 0,
  UNIQUE(product_no, option_name, sales_date)
);
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
);
"""

def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

class DB:
    def __init__(self, path: str):
        self.path = Path(path)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.init()

    def init(self):
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def upsert_products(self, rows):
        sql = """
        INSERT INTO products(product_no, product_name, category, image_url, cafe24_display_status,
          cafe24_selling_status, cafe24_soldout_status, season_tags, supplier_name, lead_time_days, safety_stock, updated_at)
        VALUES(:product_no,:product_name,:category,:image_url,:cafe24_display_status,
          :cafe24_selling_status,:cafe24_soldout_status,:season_tags,:supplier_name,:lead_time_days,:safety_stock,:updated_at)
        ON CONFLICT(product_no) DO UPDATE SET
          product_name=excluded.product_name, category=excluded.category, image_url=excluded.image_url,
          cafe24_display_status=excluded.cafe24_display_status, cafe24_selling_status=excluded.cafe24_selling_status,
          cafe24_soldout_status=excluded.cafe24_soldout_status, season_tags=excluded.season_tags,
          supplier_name=excluded.supplier_name, lead_time_days=excluded.lead_time_days,
          safety_stock=excluded.safety_stock, updated_at=excluded.updated_at;
        """
        self.conn.executemany(sql, rows)
        self.conn.commit()

    def insert_inventory_snapshots(self, rows):
        sql = """INSERT INTO inventory_snapshots(product_no, option_name, cafe24_stock, sellmate_stock, cafe24_soldout_status, captured_at)
                 VALUES(:product_no,:option_name,:cafe24_stock,:sellmate_stock,:cafe24_soldout_status,:captured_at)"""
        self.conn.executemany(sql, rows)
        self.conn.commit()

    def upsert_sales_daily(self, rows):
        sql = """
        INSERT INTO sales_daily(product_no, option_name, sales_date, order_qty, shipped_qty, returned_qty)
        VALUES(:product_no,:option_name,:sales_date,:order_qty,:shipped_qty,:returned_qty)
        ON CONFLICT(product_no, option_name, sales_date) DO UPDATE SET
          order_qty=excluded.order_qty, shipped_qty=excluded.shipped_qty, returned_qty=excluded.returned_qty;
        """
        self.conn.executemany(sql, rows)
        self.conn.commit()

    def replace_alerts(self, rows):
        self.conn.execute("DELETE FROM alerts WHERE status='open'")
        if rows:
            sql = """INSERT INTO alerts(alert_type, product_no, option_name, severity, message, status, created_at)
                     VALUES(:alert_type,:product_no,:option_name,:severity,:message,'open',:created_at)"""
            self.conn.executemany(sql, rows)
        self.conn.commit()

    def df(self, query, params=None):
        return pd.read_sql_query(query, self.conn, params=params or {})
