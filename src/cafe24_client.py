import requests
from datetime import datetime, timedelta
from urllib.parse import urlencode

class Cafe24Client:
    def __init__(self, mall_id, client_id, client_secret, redirect_uri, access_token=None, refresh_token=None, api_version="2025-12-01"):
        self.mall_id = mall_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.api_version = api_version

    @property
    def base(self):
        if not self.mall_id:
            raise ValueError("cafe24 mall_id가 없습니다.")
        return f"https://{self.mall_id}.cafe24api.com/api/v2"

    def auth_url(self, scopes):
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": ",".join(scopes),
        }
        return f"{self.base}/oauth/authorize?{urlencode(params)}"

    def exchange_code(self, code):
        url = f"{self.base}/oauth/token"
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        r = requests.post(url, data=data, timeout=30)
        if r.status_code >= 400:
            raise Exception(r.text)
        return r.json()

    def headers(self):
        if not self.access_token:
            raise ValueError("access_token이 없습니다. 먼저 토큰을 발급해 Streamlit Secrets에 저장하세요.")
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-Cafe24-Api-Version": self.api_version,
        }

    def fetch_products(self, limit=100):
        url = f"{self.base}/admin/products"
        r = requests.get(url, headers=self.headers(), params={"limit": limit}, timeout=30)
        if r.status_code >= 400:
            raise Exception(r.text)
        return r.json()

    def fetch_orders(self, days=14, limit=100):
        end = datetime.now()
        start = end - timedelta(days=days)
        url = f"{self.base}/admin/orders"
        params = {
            "start_date": start.strftime("%Y-%m-%d"),
            "end_date": end.strftime("%Y-%m-%d"),
            "limit": limit,
        }
        r = requests.get(url, headers=self.headers(), params=params, timeout=30)
        if r.status_code >= 400:
            raise Exception(r.text)
        return r.json()

    def normalize_products(self, payload):
        products = payload.get("products", []) if isinstance(payload, dict) else []
        rows, inv = [], []
        for p in products:
            product_no = str(p.get("product_no") or p.get("product_code") or "")
            rows.append({
                "product_no": product_no,
                "product_name": p.get("product_name") or p.get("name"),
                "category": "",
                "image_url": p.get("detail_image") or "",
                "display_status": p.get("display") or p.get("display_status") or "T",
                "selling_status": p.get("selling") or p.get("selling_status") or "T",
                "season_tags": "",
                "lead_time_days": 3,
                "safety_stock": 5,
            })
            stock = p.get("stock_quantity") or p.get("quantity") or 0
            soldout = p.get("sold_out") or p.get("soldout") or "F"
            inv.append({
                "product_no": product_no,
                "option_name": "",
                "cafe24_stock": stock,
                "soldout_status": soldout,
            })
        return rows, inv

    def normalize_orders(self, payload):
        orders = payload.get("orders", []) if isinstance(payload, dict) else []
        rows = []
        for o in orders:
            date = (o.get("order_date") or o.get("created_date") or "")[:10]
            items = o.get("items") or o.get("order_items") or []
            if not items and o.get("product_no"):
                items = [o]
            for it in items:
                product_no = str(it.get("product_no") or it.get("product_code") or "")
                qty = it.get("quantity") or it.get("qty") or 1
                if product_no and date:
                    rows.append({
                        "product_no": product_no,
                        "option_name": it.get("option_value") or it.get("option_name") or "",
                        "sales_date": date,
                        "order_qty": qty,
                    })
        return rows
