import base64
import time
import requests
from datetime import datetime, timedelta
from urllib.parse import urlencode
from .utils import norm_text, clean_excel_text

class Cafe24Error(Exception):
    pass

class Cafe24AuthError(Cafe24Error):
    pass

class Cafe24Client:
    def __init__(self, mall_id, client_id, client_secret, redirect_uri, access_token=None, refresh_token=None, api_version="2026-03-01"):
        self.mall_id = (mall_id or "").strip()
        self.client_id = (client_id or "").strip()
        self.client_secret = (client_secret or "").strip()
        self.redirect_uri = (redirect_uri or "").strip()
        self.access_token = (access_token or "").strip()
        self.refresh_token = (refresh_token or "").strip()
        self.api_version = (api_version or "2026-03-01").strip()
        self.last_token = None

    @property
    def base(self):
        if not self.mall_id:
            raise ValueError("cafe24 mall_id가 없습니다.")
        return f"https://{self.mall_id}.cafe24api.com/api/v2"

    def auth_url(self, scopes):
        return f"{self.base}/oauth/authorize?" + urlencode({
            "response_type": "code", "client_id": self.client_id, "redirect_uri": self.redirect_uri, "scope": ",".join(scopes)
        })

    def _basic_auth_headers(self):
        if not self.client_id or not self.client_secret:
            raise ValueError("client_id/client_secret이 비어 있습니다. Streamlit Secrets 값을 확인하세요.")
        token = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        return {"Authorization": f"Basic {token}", "Content-Type": "application/x-www-form-urlencoded"}

    def _raise_token_error(self, r):
        text = r.text
        if r.status_code in (400, 401) and ("invalid_client" in text or "invalid_grant" in text):
            raise Cafe24AuthError(text)
        raise Cafe24Error(text)

    def exchange_code(self, code):
        r = requests.post(f"{self.base}/oauth/token", headers=self._basic_auth_headers(), data={
            "grant_type": "authorization_code", "code": str(code).strip(), "redirect_uri": self.redirect_uri,
        }, timeout=30)
        if r.status_code >= 400: self._raise_token_error(r)
        self.last_token = r.json(); return self.last_token

    def refresh_access_token(self):
        if not self.refresh_token:
            raise Cafe24AuthError("refresh_token이 없습니다. 최초 인증을 다시 진행하세요.")
        r = requests.post(f"{self.base}/oauth/token", headers=self._basic_auth_headers(), data={
            "grant_type": "refresh_token", "refresh_token": self.refresh_token,
        }, timeout=30)
        if r.status_code >= 400: self._raise_token_error(r)
        tok = r.json(); self.last_token = tok
        self.access_token = tok.get("access_token", self.access_token)
        self.refresh_token = tok.get("refresh_token", self.refresh_token)
        return tok

    def headers(self):
        if not self.access_token:
            raise Cafe24AuthError("access_token이 없습니다. 최초 인증 또는 refresh_token 갱신이 필요합니다.")
        return {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json", "X-Cafe24-Api-Version": self.api_version}

    def _request(self, method, path, params=None, retry=True):
        url = path if path.startswith("http") else f"{self.base}{path}"
        r = requests.request(method, url, headers=self.headers(), params=params or {}, timeout=40)
        if r.status_code == 429:
            time.sleep(1.5)
            r = requests.request(method, url, headers=self.headers(), params=params or {}, timeout=40)
        if r.status_code in (401, 403) and retry and self.refresh_token:
            self.refresh_access_token()
            return self._request(method, path, params, retry=False)
        if r.status_code >= 400:
            text = r.text
            if r.status_code in (401, 403):
                raise Cafe24AuthError(text)
            raise Cafe24Error(text)
        return r.json()

    def _get(self, path, params=None):
        return self._request("GET", path, params)

    def fetch_all_products(self, limit=100, max_pages=50):
        """
        Cafe24 list APIs reject offset >= 5000.
        상품 수가 많은 쇼핑몰에서도 앱이 죽지 않도록 5000 직전에 안전 중단합니다.
        대부분의 운영 판단은 최근/진열 상품 중심이라 5000개 한도 내에서도 우선 동기화가 가능합니다.
        """
        rows=[]; offset=0; limit=min(int(limit or 100), 100)
        for _ in range(max_pages):
            if offset >= 5000:
                break
            data = self._get("/admin/products", {"limit": limit, "offset": offset})
            part = data.get("products", []) if isinstance(data, dict) else []
            rows.extend(part)
            if len(part) < limit: break
            offset += limit
        return rows

    def fetch_options(self, product_no): return self._get(f"/admin/products/{product_no}/options")
    def fetch_variants(self, product_no): return self._get(f"/admin/products/{product_no}/variants")

    @staticmethod
    def _to_int(v):
        try: return int(float(str(v).replace(",", "").strip()))
        except Exception: return 0

    def _list_from_payload(self, data):
        if not isinstance(data, dict): return []
        for k in ["options", "option", "variants", "items", "product_options"]:
            if isinstance(data.get(k), list): return data[k]
        return []

    def _option_name(self, obj):
        if not isinstance(obj, dict): return ""
        vals=[]
        for k in ["option_name", "option_value", "option_text", "variant_name", "item_name", "name"]:
            if obj.get(k): return clean_excel_text(obj.get(k))
        val = obj.get("option_values") or obj.get("options")
        if isinstance(val, list):
            for x in val:
                vals.append(clean_excel_text(x.get("option_text") or x.get("value") or x.get("option_value") if isinstance(x, dict) else x))
        return " / ".join([v for v in vals if v])

    def _qty(self, obj):
        if not isinstance(obj, dict): return 0
        for k in ["stock_quantity", "quantity", "inventory_quantity", "available_quantity", "stock", "option_stock_quantity", "item_stock_quantity"]:
            if k in obj: return self._to_int(obj.get(k))
        inv = obj.get("inventory")
        if isinstance(inv, dict):
            for k in ["stock_quantity", "quantity", "available_quantity", "inventory_quantity"]:
                if k in inv: return self._to_int(inv.get(k))
        return 0

    def _soldout(self, obj, qty):
        if isinstance(obj, dict):
            for k in ["soldout", "sold_out", "soldout_status", "use_soldout", "soldout_yn"]:
                if obj.get(k) is not None: return clean_excel_text(obj.get(k))
        return "T" if qty <= 0 else "F"

    def get_option_inventory_rows(self, product_no, product_name=""):
        result=[]
        for fetcher in [self.fetch_options, self.fetch_variants]:
            try:
                rows=[]
                for obj in self._list_from_payload(fetcher(product_no)):
                    qty = self._qty(obj)
                    oname = self._option_name(obj)
                    rows.append({"product_no": str(product_no), "product_name": product_name, "product_key": norm_text(product_name),
                                 "option_name": oname, "option_key": norm_text(oname), "cafe24_stock": qty, "soldout_status": self._soldout(obj, qty)})
                if rows:
                    result = rows
                    # options API가 모두 0이면 variants를 한 번 더 시도하기 위해 continue
                    if sum(r["cafe24_stock"] for r in rows) != 0: break
            except Exception:
                continue
        return result

    def normalize_products_with_inventory(self, products):
        product_rows=[]; inv_rows=[]
        for p in products:
            no = str(p.get("product_no") or p.get("product_code") or "").strip()
            if not no: continue
            name = clean_excel_text(p.get("product_name") or p.get("name") or "")
            row = {"product_no": no, "product_name": name, "product_key": norm_text(name), "category": clean_excel_text(p.get("category_name") or ""),
                   "image_url": p.get("detail_image") or p.get("image_url") or p.get("list_image") or "",
                   "display_status": clean_excel_text(p.get("display") or p.get("display_status") or p.get("display_yn") or ""),
                   "selling_status": clean_excel_text(p.get("selling") or p.get("selling_status") or p.get("selling_yn") or ""),
                   "product_soldout": clean_excel_text(p.get("soldout") or p.get("sold_out") or p.get("soldout_status") or ""),
                   "supplier_name": clean_excel_text(p.get("supplier_name") or ""), "lead_time_days": 5, "safety_stock": 5}
            product_rows.append(row)
            opts = self.get_option_inventory_rows(no, name)
            if not opts:
                qty = self._to_int(p.get("stock_quantity") or p.get("quantity") or 0)
                opts = [{"product_no": no, "product_name": name, "product_key": norm_text(name), "option_name": "", "option_key": "", "cafe24_stock": qty,
                         "soldout_status": row["product_soldout"] or ("T" if qty <= 0 else "F")}]
            inv_rows.extend(opts)
        return product_rows, inv_rows

    def fetch_orders(self, days=30, limit=100, max_pages=50):
        """
        Cafe24 주문 목록은 offset 5000 이상을 허용하지 않습니다.
        30일 주문을 한 번에 offset으로 넘기면 주문 많은 기간에 422가 발생하므로,
        날짜를 하루 단위로 쪼개고 각 날짜 안에서도 offset < 5000까지만 조회합니다.
        """
        limit=min(int(limit or 100), 100)
        end_day = datetime.now().date()
        start_day = end_day - timedelta(days=int(days or 30))
        orders=[]
        cur = start_day
        while cur <= end_day:
            offset=0; pages=0
            next_day = cur + timedelta(days=1)
            while pages < max_pages and offset < 5000:
                data = self._get("/admin/orders", {
                    "start_date": cur.strftime("%Y-%m-%d"),
                    "end_date": next_day.strftime("%Y-%m-%d"),
                    "limit": limit,
                    "offset": offset,
                })
                part = data.get("orders", []) if isinstance(data, dict) else []
                orders.extend(part)
                if len(part) < limit:
                    break
                offset += limit
                pages += 1
            cur = next_day
        return orders

    def normalize_orders(self, orders):
        rows=[]
        for o in orders:
            day = (o.get("order_date") or o.get("created_date") or o.get("ordered_date") or "")[:10]
            items = o.get("items") or o.get("order_items") or o.get("products") or []
            if not items and (o.get("product_no") or o.get("product_name")): items=[o]
            for it in items:
                name=clean_excel_text(it.get("product_name") or it.get("name") or "")
                oname=clean_excel_text(it.get("option_value") or it.get("option_name") or "")
                qty=self._to_int(it.get("quantity") or it.get("qty") or 1)
                if day and qty:
                    rows.append({"product_no": str(it.get("product_no") or it.get("product_code") or ""), "product_name": name, "product_key": norm_text(name),
                                 "option_name": oname, "option_key": norm_text(oname), "sales_date": day, "order_qty": qty})
        return rows
