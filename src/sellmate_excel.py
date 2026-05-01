import pandas as pd

COLUMN_CANDIDATES = {
    "product_no": ["product_no", "상품코드", "상품번호", "판매처상품코드", "자체상품코드", "품목코드", "코드"],
    "product_name": ["product_name", "상품명", "품목명", "제품명"],
    "option_name": ["option_name", "옵션명", "옵션", "색상/사이즈", "품목옵션"],
    "sellmate_stock": ["sellmate_stock", "재고", "현재고", "실재고", "가용재고", "재고수량", "수량"],
}

def _read(file):
    name = getattr(file, "name", "")
    if name.lower().endswith(".csv"):
        return pd.read_csv(file)
    return pd.read_excel(file)

def _find_col(df, candidates):
    norm = {str(c).strip().lower(): c for c in df.columns}
    for cand in candidates:
        key = cand.strip().lower()
        if key in norm:
            return norm[key]
    for col in df.columns:
        c = str(col).strip().lower()
        for cand in candidates:
            if cand.strip().lower() in c:
                return col
    return None

def parse_sellmate_excel(file):
    df = _read(file)
    if df.empty:
        raise ValueError("엑셀에 데이터가 없습니다.")

    mapped = {}
    for target, cands in COLUMN_CANDIDATES.items():
        col = _find_col(df, cands)
        if col is not None:
            mapped[target] = col

    if "product_no" not in mapped:
        raise ValueError("상품코드 컬럼을 찾지 못했습니다. 엑셀에 상품코드/상품번호/판매처상품코드 중 하나가 필요합니다.")
    if "sellmate_stock" not in mapped:
        raise ValueError("재고 컬럼을 찾지 못했습니다. 엑셀에 재고/현재고/실재고/재고수량 중 하나가 필요합니다.")

    out = pd.DataFrame()
    out["product_no"] = df[mapped["product_no"]].astype(str).str.strip()
    out["product_name"] = df[mapped["product_name"]].astype(str).str.strip() if "product_name" in mapped else ""
    out["option_name"] = df[mapped["option_name"]].astype(str).str.strip() if "option_name" in mapped else ""
    out["sellmate_stock"] = pd.to_numeric(df[mapped["sellmate_stock"]], errors="coerce").fillna(0).astype(int)

    out = out[out["product_no"].notna() & (out["product_no"] != "") & (out["product_no"].str.lower() != "nan")]
    out = out.groupby(["product_no", "product_name", "option_name"], as_index=False)["sellmate_stock"].sum()
    return out
