import base64
from datetime import date, timedelta
from urllib.parse import urlencode
import requests

class Cafe24Client:
    def __init__(self, mall_id, client_id, client_secret, redirect_uri, access_token="", refresh_token="", api_version="2025-12-01"):
        self.mall_id = mall_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.api_version = api_version
        self.base = f"https://{mall_id}.cafe24api.com/api/v2/admin"

    def auth_url(self, scopes: list[str]):
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "state": "selleros_inventory_radar",
            "redirect_uri": self.redirect_uri,
            "scope": ",".join(scopes),
        }
        return f"https://{self.mall_id}.cafe24api.com/api/v2/oauth/authorize?{urlencode(params)}"

    def _basic_auth(self):
        raw = f"{self.client_id}:{self.client_secret}".encode()
        return base64.b64encode(raw).decode()

    def exchange_code(self, code: str):
        url = f"https://{self.mall_id}.cafe24api.com/api/v2/oauth/token"
        headers = {
            "Authorization": f"Basic {self._basic_auth()}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {"grant_type": "authorization_code", "code": code, "redirect_uri": self.redirect_uri}
        r = requests.post(url, headers=headers, data=data, timeout=30)
        r.raise_for_status()
        return r.json()

    def refresh_access_token(self):
        if not self.refresh_token:
            raise ValueError("refresh_token이 없습니다.")
        url = f"https://{self.mall_id}.cafe24api.com/api/v2/oauth/token"
        headers = {
            "Authorization": f"Basic {self._basic_auth()}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {"grant_type": "refresh_token", "refresh_token": self.refresh_token}
        r = requests.post(url, headers=headers, data=data, timeout=30)
        r.raise_for_status()
        return r.json()

    def _get(self, endpoint: str, params=None):
        if not self.access_token:
            raise ValueError("Cafe24 access_token이 설정되지 않았습니다.")
        headers = {"Authorization": f"Bearer {self.access_token}", "X-Cafe24-Api-Version": self.api_version}
        r = requests.get(f"{self.base}{endpoint}", headers=headers, params=params or {}, timeout=45)
        r.raise_for_status()
        return r.json()

    def fetch_products(self, limit=100, offset=0):
        # Cafe24 응답 필드는 몰/버전별로 일부 차이가 있을 수 있어 normalize에서 방어적으로 처리합니다.
        return self._get("/products", {"limit": limit, "offset": offset})

    def fetch_orders(self, days=14, limit=100, offset=0):
        end = date.today()
        start = end - timedelta(days=days)
        return self._get("/orders", {
            "start_date": start.isoformat(), "end_date": end.isoformat(),
            "limit": limit, "offset": offset
        })

    @staticmethod
    def normalize_products(payload):
        items = payload.get("products", []) if isinstance(payload, dict) else []
        rows, inv = [], []
        from src.db import now_iso
        from src.season_rules import infer_tags
        for p in items:
            product_no = str(p.get("product_no") or p.get("id") or "")
            if not product_no:
                continue
            name = p.get("product_name") or p.get("name") or ""
            category = str(p.get("category") or p.get("category_name") or "")
            display = str(p.get("display") or p.get("display_status") or "")
            selling = str(p.get("selling") or p.get("selling_status") or "")
            soldout = str(p.get("soldout") or p.get("soldout_status") or "")
            stock = p.get("quantity") or p.get("stock") or p.get("stock_quantity") or 0
            try:
                stock = int(stock)
            except Exception:
                stock = 0
            rows.append({
                "product_no": product_no, "product_name": name, "category": category,
                "image_url": p.get("tiny_image") or p.get("image") or "",
                "cafe24_display_status": display, "cafe24_selling_status": selling,
                "cafe24_soldout_status": soldout, "season_tags": infer_tags(name, category),
                "supplier_name": str(p.get("supplier_name") or ""), "lead_time_days": 3,
                "safety_stock": 5, "updated_at": now_iso()
            })
            inv.append({"product_no": product_no, "option_name": "기본", "cafe24_stock": stock, "sellmate_stock": None, "cafe24_soldout_status": soldout, "captured_at": now_iso()})
        return rows, inv

    @staticmethod
    def normalize_orders(payload):
        # 실제 Cafe24 주문 응답의 item 구조는 권한/버전에 따라 다를 수 있습니다. 우선 product_no/quantity를 최대한 추출합니다.
        orders = payload.get("orders", []) if isinstance(payload, dict) else []
        from collections import defaultdict
        daily = defaultdict(int)
        for order in orders:
            order_date = (order.get("order_date") or order.get("created_date") or "")[:10]
            items = order.get("items") or order.get("order_items") or []
            if not items and order.get("product_no"):
                items = [order]
            for it in items:
                product_no = str(it.get("product_no") or it.get("product_id") or "")
                if not product_no or not order_date:
                    continue
                option_name = str(it.get("option_value") or it.get("option_name") or "기본")
                qty = it.get("quantity") or it.get("order_qty") or 1
                try:
                    qty = int(qty)
                except Exception:
                    qty = 1
                daily[(product_no, option_name, order_date)] += qty
        return [{"product_no": k[0], "option_name": k[1], "sales_date": k[2], "order_qty": v, "shipped_qty": 0, "returned_qty": 0} for k, v in daily.items()]
