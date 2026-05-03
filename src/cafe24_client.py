import base64
import requests
from datetime import datetime, timedelta
from urllib.parse import urlencode

class Cafe24Client:
    def __init__(self, mall_id, client_id, client_secret, redirect_uri, access_token=None, refresh_token=None, api_version="2026-03-01"):
        self.mall_id = mall_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.api_version = api_version or "2026-03-01"

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

    def _basic_auth_headers(self):
        raw = f"{self.client_id}:{self.client_secret}"
        encoded = base64.b64encode(raw.encode("utf-8")).decode("utf-8")
        return {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def exchange_code(self, code):
        r = requests.post(
            f"{self.base}/oauth/token",
            headers=self._basic_auth_headers(),
            data={
                "grant_type": "authorization_code",
                "code": str(code).strip(),
                "redirect_uri": self.redirect_uri,
            },
            timeout=30,
        )
        if r.status_code >= 400:
            raise Exception(r.text)
        return r.json()

    def refresh_access_token(self):
        if not self.refresh_token:
            raise ValueError("refresh_token이 없습니다.")
        r = requests.post(
            f"{self.base}/oauth/token",
            headers=self._basic_auth_headers(),
            data={"grant_type": "refresh_token", "refresh_token": self.refresh_token},
            timeout=30,
        )
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

    def _get(self, url, params=None):
        r = requests.get(url, headers=self.headers(), params=params or {}, timeout=30)
        if r.status_code >= 400:
            raise Exception(r.text)
        return r.json()

    def fetch_products(self, limit=100, offset=0):
        return self._get(f"{self.base}/admin/products", {"limit": limit, "offset": offset})

    def fetch_options(self, product_no):
        return self._get(f"{self.base}/admin/products/{product_no}/options")

    def fetch_variants(self, product_no):
        return self._get(f"{self.base}/admin/products/{product_no}/variants")

    def _to_int(self, value):
        try:
            if value is None:
                return 0
            return int(str(value).replace(",", "").strip())
        except Exception:
            return 0

    def _pick_qty(self, obj):
        if not isinstance(obj, dict):
            return 0
        for key in [
            "stock_quantity", "quantity", "inventory_quantity", "available_quantity",
            "stock", "option_stock_quantity", "item_stock_quantity", "product_quantity",
        ]:
            if key in obj:
                return self._to_int(obj.get(key))
        inv = obj.get("inventory")
        if isinstance(inv, dict):
            for key in ["stock_quantity", "quantity", "available_quantity", "inventory_quantity"]:
                if key in inv:
                    return self._to_int(inv.get(key))
        return 0

    def _option_name(self, obj):
        if not isinstance(obj, dict):
            return ""
        for key in ["option_name", "option_value", "option_text", "variant_name", "item_name", "name"]:
            val = obj.get(key)
            if val:
                if isinstance(val, list):
                    return " / ".join(str(x) for x in val)
                return str(val)
        val = obj.get("option_values") or obj.get("options")
        if val:
            if isinstance(val, list):
                return " / ".join(
                    str(x.get("option_text", x.get("value", x))) if isinstance(x, dict) else str(x)
                    for x in val
                )
            return str(val)
        return ""

    def _soldout_status(self, obj, qty):
        if isinstance(obj, dict):
            for key in ["soldout", "sold_out", "soldout_status", "use_soldout"]:
                if key in obj and obj.get(key) is not None:
                    return str(obj.get(key))
        return "T" if qty <= 0 else "F"

    def _extract_list(self, data):
        if not isinstance(data, dict):
            return []
        for key in ["options", "option", "items", "variants", "product_options"]:
            val = data.get(key)
            if isinstance(val, list):
                return val
        return []

    def get_option_inventory_rows(self, product_no):
        rows = []
        try:
            data = self.fetch_options(product_no)
            for obj in self._extract_list(data):
                qty = self._pick_qty(obj)
                rows.append({
                    "product_no": str(product_no),
                    "option_name": self._option_name(obj),
                    "cafe24_stock": qty,
                    "soldout_status": self._soldout_status(obj, qty),
                })
        except Exception:
            rows = []

        if not rows or sum(r["cafe24_stock"] for r in rows) == 0:
            try:
                data = self.fetch_variants(product_no)
                variant_rows = []
                for obj in self._extract_list(data):
                    qty = self._pick_qty(obj)
                    variant_rows.append({
                        "product_no": str(product_no),
                        "option_name": self._option_name(obj),
                        "cafe24_stock": qty,
                        "soldout_status": self._soldout_status(obj, qty),
                    })
                if variant_rows:
                    rows = variant_rows
            except Exception:
                pass
        return rows

    def fetch_orders(self, days=14, limit=100):
        end = datetime.now()
        start = end - timedelta(days=days)
        return self._get(f"{self.base}/admin/orders", {
            "start_date": start.strftime("%Y-%m-%d"),
            "end_date": end.strftime("%Y-%m-%d"),
            "limit": limit,
        })

    def normalize_products_with_option_stock(self, payload):
        products = payload.get("products", []) if isinstance(payload, dict) else []
        product_rows, inventory_rows = [], []
        for p in products:
            product_no = str(p.get("product_no") or p.get("product_code") or "")
            if not product_no:
                continue
            product_rows.append({
                "product_no": product_no,
                "product_name": p.get("product_name") or p.get("name") or "",
                "category": "",
                "image_url": p.get("detail_image") or p.get("image_url") or "",
                "display_status": p.get("display") or p.get("display_status") or "T",
                "selling_status": p.get("selling") or p.get("selling_status") or "T",
                "season_tags": "",
                "lead_time_days": 3,
                "safety_stock": 5,
            })
            option_rows = self.get_option_inventory_rows(product_no)
            if not option_rows:
                qty = self._to_int(p.get("stock_quantity") or p.get("quantity") or 0)
                option_rows = [{
                    "product_no": product_no,
                    "option_name": "",
                    "cafe24_stock": qty,
                    "soldout_status": "T" if qty <= 0 else "F",
                }]
            inventory_rows.extend(option_rows)
        return product_rows, inventory_rows

    def normalize_orders(self, payload):
        orders = payload.get("orders", []) if isinstance(payload, dict) else []
        rows = []
        for o in orders:
            order_date = (o.get("order_date") or o.get("created_date") or o.get("ordered_date") or "")[:10]
            items = o.get("items") or o.get("order_items") or []
            if not items and o.get("product_no"):
                items = [o]
            for it in items:
                product_no = str(it.get("product_no") or it.get("product_code") or "")
                qty = it.get("quantity") or it.get("qty") or 1
                if product_no and order_date:
                    rows.append({
                        "product_no": product_no,
                        "option_name": it.get("option_value") or it.get("option_name") or "",
                        "sales_date": order_date,
                        "order_qty": qty,
                    })
        return rows
