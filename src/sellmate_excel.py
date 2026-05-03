import io
import pandas as pd
from .utils import clean_excel_text, norm_text

COLUMN_CANDIDATES = {
    "supplier_name": ["공급처", "거래처", "supplier"],
    "product_no": ["product_no", "상품코드", "상품번호", "판매처상품코드", "자체상품코드", "품목코드", "코드"],
    "product_name": ["상품명", "product_name", "품목명", "제품명"],
    "purchase_name": ["사입상품명", "공급처상품명", "매입상품명"],
    "option_name": ["옵션명", "옵션", "색상/사이즈", "품목옵션", "option_name"],
    "sellmate_stock": ["가용재고", "현재재고", "현재고", "실재고", "재고수량", "재고", "수량", "sellmate_stock"],
    "current_stock": ["현재재고", "현재고"],
    "unshipped_qty": ["미발송주문수", "미배송", "미발송"],
    "sellmate_soldout": ["품절여부", "품절"],
    "sellmate_selling": ["판매여부", "판매"],
    "cost": ["원가"],
    "price": ["대표판매가", "판매가"],
}


def _read_csv_bytes(file):
    raw = file.getvalue() if hasattr(file, "getvalue") else file.read()
    last = None
    for enc in ["cp949", "euc-kr", "utf-8-sig", "utf-8"]:
        try:
            return pd.read_csv(io.BytesIO(raw), encoding=enc), enc
        except Exception as e:
            last = e
    text = raw.decode("cp949", errors="replace")
    return pd.read_csv(io.StringIO(text)), f"cp949-replace ({last})"


def _read(file):
    name = getattr(file, "name", "").lower()
    if name.endswith(".csv"):
        return _read_csv_bytes(file)
    return pd.read_excel(file), "excel"


def _find_col(df, candidates):
    norm_cols = {str(c).strip().lower(): c for c in df.columns}
    for cand in candidates:
        if cand.strip().lower() in norm_cols:
            return norm_cols[cand.strip().lower()]
    for col in df.columns:
        c = str(col).strip().lower()
        for cand in candidates:
            if cand.strip().lower() in c:
                return col
    return None


def _to_int_series(s):
    return pd.to_numeric(
        s.astype(str).str.replace(",", "", regex=False).str.replace("=", "", regex=False).str.replace('"', "", regex=False).str.strip(),
        errors="coerce",
    ).fillna(0).astype(int)


def parse_sellmate_stock_file(file):
    df, encoding = _read(file)
    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]
    if df.empty:
        raise ValueError("파일에 데이터가 없습니다.")

    mapped = {target: col for target, cands in COLUMN_CANDIDATES.items() if (col := _find_col(df, cands)) is not None}
    if "product_name" not in mapped:
        raise ValueError("셀메이트 파일에서 '상품명' 컬럼을 찾지 못했습니다.")
    if "sellmate_stock" not in mapped:
        raise ValueError("재고 컬럼을 찾지 못했습니다. 보통 '가용재고' 또는 '현재재고'가 필요합니다.")

    out = pd.DataFrame()
    out["product_name"] = df[mapped["product_name"]].map(clean_excel_text)
    out["product_no"] = df[mapped["product_no"]].map(clean_excel_text) if "product_no" in mapped else ""
    out["product_no"] = out["product_no"].replace({"nan": "", "None": "", "NaN": ""}).fillna("")
    out["product_key"] = out["product_name"].map(norm_text)
    out["purchase_name"] = df[mapped["purchase_name"]].map(clean_excel_text) if "purchase_name" in mapped else ""
    out["option_name"] = df[mapped["option_name"]].map(clean_excel_text) if "option_name" in mapped else ""
    out["option_key"] = out["option_name"].map(norm_text)
    out["supplier_name"] = df[mapped["supplier_name"]].map(clean_excel_text) if "supplier_name" in mapped else ""
    out["sellmate_stock"] = _to_int_series(df[mapped["sellmate_stock"]])
    out["current_stock"] = _to_int_series(df[mapped["current_stock"]]) if "current_stock" in mapped else out["sellmate_stock"]
    out["unshipped_qty"] = _to_int_series(df[mapped["unshipped_qty"]]) if "unshipped_qty" in mapped else 0
    out["sellmate_soldout"] = df[mapped["sellmate_soldout"]].map(clean_excel_text) if "sellmate_soldout" in mapped else ""
    out["sellmate_selling"] = df[mapped["sellmate_selling"]].map(clean_excel_text) if "sellmate_selling" in mapped else ""
    out["cost"] = _to_int_series(df[mapped["cost"]]) if "cost" in mapped else 0
    out["price"] = _to_int_series(df[mapped["price"]]) if "price" in mapped else 0

    out = out[(out["product_name"] != "") & (out["product_key"] != "")]
    group_cols = ["product_no", "product_name", "product_key", "purchase_name", "option_name", "option_key", "supplier_name", "sellmate_soldout", "sellmate_selling"]
    out = out.groupby(group_cols, as_index=False, dropna=False).agg({
        "sellmate_stock": "sum", "current_stock": "sum", "unshipped_qty": "sum", "cost": "max", "price": "max"
    })
    return out, list(df.columns), encoding
