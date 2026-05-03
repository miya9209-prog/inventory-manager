import re
try:
    import streamlit as st
except Exception:
    class _DummySt:
        secrets = {}
    st = _DummySt()


def get_secret(section: str, key: str, default=None):
    try:
        if section in st.secrets and key in st.secrets[section]:
            val = st.secrets[section][key]
            return str(val).strip() if isinstance(val, str) else val
    except Exception:
        pass
    try:
        flat_key = f"{section.upper()}_{key.upper()}"
        val = st.secrets.get(flat_key, default)
        return str(val).strip() if isinstance(val, str) else val
    except Exception:
        return default


def clean_excel_text(value):
    s = "" if value is None else str(value).strip()
    # 셀메이트 CSV에 ="상품명" 형태가 들어오는 경우 처리
    if s.startswith('="') and s.endswith('"'):
        s = s[2:-1]
    return s.strip().strip('"').strip()


def norm_text(value):
    s = clean_excel_text(value).lower()
    s = re.sub(r"\([^)]*\)", "", s)  # (4 color) 같은 표현 제거
    s = re.sub(r"\[[^]]*\]", "", s)
    s = re.sub(r"[^0-9a-z가-힣]+", "", s)
    return s


def truthy_status(value):
    s = clean_excel_text(value).upper()
    return s in {"T", "Y", "TRUE", "1", "품절", "SOLDOUT", "SOLD_OUT", "S"}


def selling_on(value):
    s = clean_excel_text(value).upper()
    return s in {"T", "Y", "TRUE", "1", "판매", "판매중", "ON", "AVAILABLE"}
