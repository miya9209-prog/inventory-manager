import streamlit as st
import pandas as pd
from src.db import DB
from src.utils import get_secret
from src.sellmate_excel import parse_sellmate_stock_file
from src.cafe24_client import Cafe24Client, Cafe24AuthError
from src.analytics import build_product_metrics, generate_alerts

st.set_page_config(page_title="미샵 재고 관제센터", page_icon="📦", layout="wide")
st.markdown("""
<style>
[data-testid="stSidebar"]{display:none}.block-container{max-width:1360px;padding-top:2.2rem}.title{font-size:38px;font-weight:900;letter-spacing:-1px}.sub{color:#666;line-height:1.7;margin:8px 0 22px}.box{border:1px solid #eee;background:#fafafa;border-radius:16px;padding:16px 18px;line-height:1.75}.danger{color:#c1121f;font-weight:800}.ok{color:#096b28;font-weight:800}
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='title'>미샵 재고 관제센터</div>", unsafe_allow_html=True)
st.markdown("<div class='sub'>셀메이트 실제 가용재고를 기준으로 카페24 상품/옵션 재고와 비교해, 실제 품절이 아닌데 카페24에서 품절 처리된 상품과 곧 확보해야 할 상품을 먼저 찾습니다.</div>", unsafe_allow_html=True)
st.markdown("""
<div class='box'>
<b>핵심 판정 기준</b><br>
1. <span class='danger'>카페24품절_실제재고있음</span> : 셀메이트 가용재고는 있는데 카페24 재고가 0이거나 품절 상태라 노출/구매 손실이 나는 상품<br>
2. <span class='danger'>실제재고없음_판매중위험</span> : 셀메이트 가용재고는 없는데 카페24에서 판매중이라 주문 사고가 날 수 있는 상품<br>
3. <span class='ok'>긴급입고필요/입고검토</span> : 최근 판매속도와 실제재고 기준으로 미리 확보해야 할 상품
</div>
""", unsafe_allow_html=True)

DB_PATH = get_secret("app", "db_path", "selleros_inventory.db")
db = DB(DB_PATH)

q = st.query_params
AUTO_CODE = q.get("code", "")
if isinstance(AUTO_CODE, list): AUTO_CODE = AUTO_CODE[0] if AUTO_CODE else ""

with st.expander("1) 셀메이트 실제 재고 DB 업데이트", expanded=True):
    uploaded = st.file_uploader("셀메이트 재고 CSV/엑셀 업로드", type=["csv", "xlsx", "xls"])
    if uploaded:
        try:
            stock_df, raw_cols, encoding = parse_sellmate_stock_file(uploaded)
            st.success(f"셀메이트 파일 인식 완료: {len(stock_df):,}개 옵션 / 인코딩: {encoding}")
            st.caption("인식 컬럼: " + ", ".join(raw_cols[:30]))
            st.dataframe(stock_df.head(80), use_container_width=True, hide_index=True)
            if st.button("셀메이트 재고 DB 반영", type="primary"):
                db.replace_sellmate_stock(stock_df)
                st.success(f"반영 완료: {len(stock_df):,}개 옵션")
                st.rerun()
        except Exception as e:
            st.error(f"셀메이트 파일 처리 실패: {e}")

with st.expander("2) 카페24 API 연결 · 상품/옵션재고/주문 동기화", expanded=False):
    mall_id = get_secret("cafe24", "mall_id")
    client_id = get_secret("cafe24", "client_id")
    client_secret = get_secret("cafe24", "client_secret")
    redirect_uri = get_secret("cafe24", "redirect_uri")
    access_token = get_secret("cafe24", "access_token")
    refresh_token = get_secret("cafe24", "refresh_token")
    api_version = get_secret("cafe24", "api_version", "2026-03-01")
    cafe = Cafe24Client(mall_id, client_id, client_secret, redirect_uri, access_token, refresh_token, api_version)

    c1, c2, c3 = st.columns(3)
    c1.metric("Mall ID", mall_id or "미설정")
    c2.metric("Access Token", "있음" if access_token else "없음")
    c3.metric("Refresh Token", "있음" if refresh_token else "없음")
    st.caption("invalid_client가 나오면 코드 문제가 아니라 대부분 Client ID/Secret 불일치, 다른 앱의 Secret 사용, Secret 앞뒤 공백, redirect_uri 불일치입니다. 이 버전은 Secrets 값을 자동 strip 처리합니다.")

    def show_new_token(token):
        st.warning("새 토큰이 발급되었습니다. 아래 값을 Streamlit Secrets의 [cafe24]에 다시 저장하세요.")
        st.json({k: token.get(k) for k in ["access_token", "refresh_token", "expires_at", "refresh_token_expires_at", "scopes"] if k in token})

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("토큰 연결 테스트"):
            try:
                products = cafe.fetch_all_products(limit=10, max_pages=1)
                if cafe.last_token: show_new_token(cafe.last_token)
                st.success(f"연결 성공: 상품 {len(products)}개 테스트 조회")
            except Cafe24AuthError as e:
                st.error(f"토큰/인증 오류: {e}")
            except Exception as e:
                st.error(f"연결 실패: {e}")
    with col_b:
        if st.button("Refresh Token으로 갱신"):
            try:
                show_new_token(cafe.refresh_access_token())
            except Exception as e:
                st.error(f"토큰 갱신 실패: {e}")
    with col_c:
        if st.button("DB 전체 초기화"):
            db.reset_all(); st.success("DB 초기화 완료"); st.rerun()

    st.divider()
    scopes = ["mall.read_product", "mall.read_order"]
    if mall_id and client_id and redirect_uri:
        st.link_button("카페24 권한 승인 URL 열기", cafe.auth_url(scopes))
    code = st.text_input("승인 후 code 붙여넣기", value=AUTO_CODE, type="password")
    if st.button("Access Token 최초 발급") and code:
        try: show_new_token(cafe.exchange_code(code))
        except Exception as e: st.error(f"토큰 발급 실패: {e}")

    st.divider()
    days = st.slider("주문 판매량 조회 기간", 7, 90, 30)
    if st.button("카페24 상품/옵션재고/주문 동기화", type="primary"):
        try:
            with st.spinner("카페24 상품과 옵션재고를 조회 중입니다."):
                products = cafe.fetch_all_products(limit=100, max_pages=100)
                product_rows, inv_rows = cafe.normalize_products_with_inventory(products)
                db.upsert_products(product_rows)
                db.insert_inventory_snapshots(inv_rows)
            with st.spinner("주문 판매량을 조회 중입니다."):
                orders = cafe.fetch_orders(days=days, limit=100, max_pages=50)
                sales_rows = cafe.normalize_orders(orders)
                db.insert_sales_daily(sales_rows)
            if cafe.last_token: show_new_token(cafe.last_token)
            st.success(f"동기화 완료: 상품 {len(product_rows):,}개 / 옵션재고 {len(inv_rows):,}건 / 주문상품 {len(sales_rows):,}건")
            st.rerun()
        except Cafe24AuthError as e:
            st.error(f"카페24 인증 오류: {e}")
        except Exception as e:
            st.error(f"동기화 실패: {e}")

metrics = build_product_metrics(db)
if metrics.empty:
    st.warning("아직 표시할 데이터가 없습니다. 먼저 셀메이트 재고 파일을 DB에 반영하세요.")
    st.stop()

alerts = generate_alerts(metrics)
db.replace_alerts(alerts)

for col in ["product_no", "상품명", "공급처", "셀메이트가용재고", "셀메이트현재재고", "미발송주문수", "카페24재고", "3일판매", "7일판매", "14일판매", "30일판매", "예상품절일", "추천입고수량", "진열", "판매", "상품품절", "옵션품절", "상태"]:
    if col not in metrics.columns: metrics[col] = ""
show_cols = ["product_no", "상품명", "공급처", "셀메이트가용재고", "셀메이트현재재고", "미발송주문수", "카페24재고", "3일판매", "7일판매", "14일판매", "30일판매", "예상품절일", "추천입고수량", "진열", "판매", "상품품절", "옵션품절", "상태"]

c1,c2,c3,c4,c5 = st.columns(5)
c1.metric("카페24 품절·실재고 있음", int((metrics["상태"]=="카페24품절_실제재고있음").sum()))
c2.metric("실재고 없음·판매중", int((metrics["상태"]=="실제재고없음_판매중위험").sum()))
c3.metric("긴급입고필요", int((metrics["상태"]=="긴급입고필요").sum()))
c4.metric("입고검토", int((metrics["상태"]=="입고검토").sum()))
c5.metric("악성재고 후보", int((metrics["상태"]=="악성재고후보").sum()))

st.divider()
tabs = st.tabs(["긴급 알림", "카페24 품절 오류", "입고 추천", "악성재고", "전체 상품", "셀메이트 원장", "카페24 옵션재고", "알림 로그"])

with tabs[0]:
    df = metrics[metrics["우선순위"] <= 2]
    st.subheader("오늘 먼저 처리할 상품")
    st.dataframe(df[show_cols], use_container_width=True, hide_index=True)
with tabs[1]:
    df = metrics[metrics["상태"]=="카페24품절_실제재고있음"]
    st.subheader("실제 재고는 있는데 카페24에서 품절/재고0으로 막힌 상품")
    st.dataframe(df[show_cols], use_container_width=True, hide_index=True)
with tabs[2]:
    df = metrics[metrics["추천입고수량"] > 0].sort_values(["우선순위", "추천입고수량"], ascending=[True, False])
    st.subheader("미리 확보해야 할 상품")
    st.caption("추천입고수량 = 최근 7일 일평균판매 × 리드타임 5일 + 안전재고 5장 - 셀메이트 가용재고")
    st.dataframe(df[show_cols], use_container_width=True, hide_index=True)
with tabs[3]:
    df = metrics[metrics["상태"]=="악성재고후보"]
    st.dataframe(df[show_cols], use_container_width=True, hide_index=True)
with tabs[4]:
    kw = st.text_input("상품명 검색")
    df = metrics if not kw else metrics[metrics["상품명"].astype(str).str.contains(kw, case=False, na=False)]
    st.dataframe(df[show_cols], use_container_width=True, hide_index=True)
with tabs[5]:
    st.dataframe(db.df("SELECT * FROM sellmate_stock ORDER BY updated_at DESC"), use_container_width=True, hide_index=True)
with tabs[6]:
    st.dataframe(db.df("SELECT * FROM inventory_snapshots WHERE id IN (SELECT MAX(id) FROM inventory_snapshots GROUP BY product_no, option_key) ORDER BY product_name, option_name"), use_container_width=True, hide_index=True)
with tabs[7]:
    st.dataframe(db.df("SELECT * FROM alerts ORDER BY id DESC"), use_container_width=True, hide_index=True)
