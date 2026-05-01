import requests

class SellmateClient:
    """셀메이트 API 어댑터.

    셀메이트는 계정/계약에 따라 제공 API 문서와 인증 헤더가 다를 수 있습니다.
    API 신청 후 받은 문서 기준으로 endpoint와 headers를 맞추면 됩니다.
    """
    def __init__(self, base_url="", api_key="", api_secret=""):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key
        self.api_secret = api_secret

    def configured(self):
        return bool(self.base_url and self.api_key)

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Api-Secret": self.api_secret or "",
        }

    def fetch_inventory(self):
        if not self.configured():
            return []
        r = requests.get(f"{self.base_url}/inventory", headers=self._headers(), timeout=45)
        r.raise_for_status()
        return r.json()

    def normalize_inventory(self, payload):
        from src.db import now_iso
        items = payload.get("items", payload if isinstance(payload, list) else [])
        rows = []
        for it in items:
            product_no = str(it.get("product_no") or it.get("product_id") or "")
            if not product_no:
                continue
            rows.append({
                "product_no": product_no,
                "option_name": str(it.get("option_name") or "기본"),
                "cafe24_stock": None,
                "sellmate_stock": int(it.get("stock") or it.get("quantity") or 0),
                "cafe24_soldout_status": "",
                "captured_at": now_iso(),
            })
        return rows
