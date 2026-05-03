import streamlit as st
import pandas as pd

from src.db import DB
from src.utils import get_secret
from src.sample_data import seed_sample_data
from src.sellmate_excel import parse_sellmate_stock_file
from src.cafe24_client import Cafe24Client
from src.analytics import (
    build_product_metrics,
    classify_metrics,
    season_open_candidates,
    generate_alerts,
)

st.set_page_config(page_title="재고 관제센터", page_icon="📦", layout="wide")

st.markdown("""
<style>
[data-testid="stSidebar"] {display:none;}
[data-testid="collapsedControl"] {display:none;}
.block-container {max-width:1240px;padding-top:3rem;padding-left:2rem;padding-right:2rem;}
.main-title {font-size:38px;font-weight:800;color:#222;margin-bottom:8px;}
.sub-title {font-size:15px;color:#666;margin-bottom:28px;line-height:1.7;}
.notice-box {border:1px solid #eee;background:#fafafa;border-radius:14px;padding:18px 20px;line-height:1.75;margin-bottom:24px;}
.small-guide {color:#666;font-size:14px;line-height:1.7;}
.stTabs [data-baseweb="tab-list"] {gap:18px;border-bottom:1px solid #ddd;margin-bottom:28px;}
.stTabs [data-baseweb="tab"] {height:52px;font-size:16px;}
div[data-testid="stMetricValue"] {font-size:32px;}
</style>
""", unsafe_allow_html=True)

DB_PATH = get_secret("app", "db_path", "selleros_inventory.db")
USE_SAMPLE = bool(get_secret("app", "use_sample_data", True))
db = DB(DB_PATH)

# 카페24 승인 후 Redirect URI로 돌아온 code 자동 감지
query_params = st.query_params
AUTO_CAFE24_CODE = query_params.get("code", "")
if isinstance(AUTO_CAFE24_CODE, list):
    AUTO_CAFE24_CODE = AUTO_CAFE24_CODE[0] if AUTO_CAFE24_CODE else ""

if AUTO_CAFE24_CODE:
    st.success("카페24 승인 code가 감지되었습니다. 아래 'Access Token 발급' 버튼을 눌러 토큰을 발급하세요.")

st.markdown("<div class='main-title'>재고 관제센터</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='sub-title'>셀메이트 실제재고 파일을 DB에 업데이트하고, 카페24 상품/주문/옵션재고와 비교해 품절위험·입고추천·시즌오픈추천·악성재고를 판단합니다.</div>",
    unsafe_allow_html=True
)

st.markdown("""
<div class='notice-box'>
<b>운영 기준</b><br>
1. 매일 오후 1~2시경 셀메이트에서 재고 CSV/엑셀을 다운로드합니다.<br>
2. 셀메이트 파일을 업로드해 <b>셀메이트 재고 DB</b>를 업데이트합니다.<br>
3. 카페24는 상품/주문/옵션재고를 동기화합니다. 옵션재고는 options API를 우선 조회하고, 안 되면 variants API로 보정합니다.<br>
4. 판단 기준은 <b>셀메이트 실제재고</b>이며, 카페24는 판매상태/품절처리/매출손실 감지용으로 사용합니다.
</div>
""", unsafe_allow_html=True)

with st.expander("1) 셀메이트 재고 DB 업데이트", expanded=True):
    st.caption("셀메이트에서 내려받은 CSV/엑셀을 그대로 업로드하세요. CP949/EUC-KR CSV도 자동 인식합니다.")
    uploaded = st.file_uploader("셀메이트 재고 파일 업로드", type=["csv", "xlsx", "xls"])

    if uploaded is not None:
        try:
            stock_df, raw_cols = parse_sellmate_stock_file(uploaded)
            st.success(f"파일 인식 완료: {len(stock_df)}건")
            st.caption(f"인식된 원본 컬럼: {', '.join(raw_cols[:20])}")
            st.dataframe(stock_df.head(100), use_container_width=True, hide_index=True)

            if st.button("셀메이트 재고 DB 업데이트", type="primary"):
                db.replace_sellmate_stock(stock_df)
                st.success(f"셀메이트 재고 DB 업데이트 완료: {len(stock_df)}건")
                st.rerun()
        except Exception as e:
            st.error(f"셀메이트 파일 처리 실패: {e}")

with st.expander("2) 카페24 상품/주문/옵션재고 동기화", expanded=False):
    st.markdown("""
    <div class='small-guide'>
    카페24는 최초 1회 권한 승인과 토큰 발급이 필요합니다.<br>
    토큰을 Streamlit Secrets에 저장한 뒤에는 평소 <b>카페24 상품/주문/옵션재고 동기화</b> 버튼만 누르면 됩니다.<br>
    API 버전은 <b>2026-03-01</b>을 기준으로 합니다.
    </div>
    """, unsafe_allow_html=True)

    mall_id = get_secret("cafe24", "mall_id")
    client_id = get_secret("cafe24", "client_id")
    client_secret = get_secret("cafe24", "client_secret")
    redirect_uri = get_secret("cafe24", "redirect_uri")
    access_token = get_secret("cafe24", "access_token")
    refresh_token = get_secret("cafe24", "refresh_token")
    api_version = get_secret("cafe24", "api_version", "2026-03-01")

    cafe = Cafe24Client(
        mall_id=mall_id,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        access_token=access_token,
        refresh_token=refresh_token,
        api_version=api_version,
    )


    def sync_cafe24_with_retry():
        """
        access_token 만료 시 refresh_token으로 새 토큰을 발급한 뒤 1회 재시도합니다.
        새 토큰은 화면에 표시되므로 Streamlit Secrets에 복사 저장해야 합니다.
        """
        try:
            products_payload = cafe.fetch_products(limit=100)
        except Exception as first_error:
            msg = str(first_error)
            if "invalid_token" in msg or "access_token time expired" in msg or "401" in msg:
                if not refresh_token:
                    raise Exception("access_token이 만료되었고 refresh_token도 없습니다. 카페24 최초 인증을 다시 진행하세요.")
                new_token = cafe.refresh_access_token()
                st.warning("access_token이 만료되어 refresh_token으로 새 토큰을 발급했습니다. 아래 값을 Streamlit Secrets에 저장하세요.")
                st.json(new_token)
                cafe.access_token = new_token.get("access_token", cafe.access_token)
                cafe.refresh_token = new_token.get("refresh_token", cafe.refresh_token)
                products_payload = cafe.fetch_products(limit=100)
            else:
                raise first_error

        product_rows, inventory_rows = cafe.normalize_products_with_option_stock(products_payload)
        db.upsert_products(product_rows)
        db.insert_inventory_snapshots(inventory_rows)

        orders_payload = cafe.fetch_orders(days=14, limit=100)
        sales_rows = cafe.normalize_orders(orders_payload)
        if sales_rows:
            db.insert_sales_daily(sales_rows)

        return product_rows, inventory_rows, sales_rows

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("카페24 상품/주문/옵션재고 동기화", type="primary"):
            try:
                product_rows, inventory_rows, sales_rows = sync_cafe24_with_retry()
                st.success(
                    f"동기화 완료: 상품 {len(product_rows)}개, 옵션재고 {len(inventory_rows)}건, 주문일별 {len(sales_rows)}건"
                )
                st.rerun()
            except Exception as e:
                st.error(f"동기화 실패: {e}")

    with col2:
        if st.button("샘플 데이터 새로 넣기"):
            seed_sample_data(db)
            st.success("샘플 데이터가 입력되었습니다.")
            st.rerun()

    with col3:
        if st.button("로컬 DB 전체 초기화"):
            db.reset_all()
            st.success("DB가 초기화되었습니다.")
            st.rerun()

    with st.expander("카페24 최초 인증/토큰 발급"):
        scopes = ["mall.read_product", "mall.read_order"]

        if mall_id and client_id and redirect_uri:
            st.link_button("카페24 권한 승인 URL 열기", cafe.auth_url(scopes))
        else:
            st.warning("Streamlit Secrets에 cafe24 mall_id/client_id/redirect_uri를 먼저 입력하세요.")

        code = st.text_input(
            "카페24 승인 후 code 붙여넣기",
            value=AUTO_CAFE24_CODE if AUTO_CAFE24_CODE else "",
            type="password",
        )

        if AUTO_CAFE24_CODE:
            st.caption("자동 감지된 code")
            st.code(AUTO_CAFE24_CODE, language="text")

        if st.button("Access Token 발급") and code:
            try:
                token = cafe.exchange_code(code)
                st.success("토큰 발급 성공. 아래 access_token / refresh_token 값을 Streamlit Secrets에 저장하세요.")
                st.json(token)
            except Exception as e:
                st.error(f"토큰 발급 실패: {e}")

        if st.button("Refresh Token으로 Access Token 갱신"):
            try:
                new_token = cafe.refresh_access_token()
                st.success("토큰 갱신 성공. 아래 access_token / refresh_token 값을 Streamlit Secrets에 저장하세요.")
                st.json(new_token)
            except Exception as e:
                st.error(f"토큰 갱신 실패: {e}")


if USE_SAMPLE and db.count_products() == 0:
    seed_sample_data(db)

metrics = classify_metrics(build_product_metrics(db))
season_df = season_open_candidates(metrics)
alerts = generate_alerts(metrics, season_df)
db.replace_alerts(alerts)

if metrics.empty:
    st.warning("아직 데이터가 없습니다. 샘플 데이터를 넣거나 셀메이트 파일 업로드/카페24 동기화를 실행하세요.")
    st.stop()

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("실제재고 품절 인기상품", int((metrics["상태"] == "실제재고품절_인기").sum()))
c2.metric("카페24 품절처리 감지", int((metrics["상태"] == "카페24품절처리_인기").sum()))
c3.metric("카페24 품절·실제재고 있음", int((metrics["상태"] == "카페24품절_실제재고있음").sum()))
c4.metric("실제재고 없음·판매중", int((metrics["상태"] == "실제재고없음_판매중위험").sum()))
c5.metric("시즌 오픈 추천", len(season_df))
c6.metric("악성재고 후보", int((metrics["상태"] == "악성재고후보").sum()))

st.divider()

tabs = st.tabs([
    "오늘의 긴급 알림",
    "품절 위험",
    "입고 추천",
    "시즌 오픈 추천",
    "악성재고 소진",
    "전체 상품",
    "셀메이트 DB",
    "카페24 옵션재고",
    "알림 로그",
])

show_cols = [
    "product_no", "상품명", "카테고리", "셀메이트재고", "카페24재고", "기준재고",
    "3일판매", "7일판매", "14일판매", "30일판매", "예상품절일", "추천입고수량",
    "진열", "판매", "품절", "상태", "시즌태그"
]

with tabs[0]:
    st.subheader("오늘 MD가 먼저 봐야 할 상품")
    urgent_states = [
        "실제재고품절_인기",
        "카페24품절처리_인기",
        "카페24품절_실제재고있음",
        "실제재고없음_판매중위험",
        "긴급품절위험",
        "품절위험",
    ]
    urgent = metrics[metrics["상태"].isin(urgent_states)]
    if urgent.empty:
        st.success("긴급 품절/입고 알림이 없습니다.")
    else:
        st.dataframe(urgent[show_cols], use_container_width=True, hide_index=True)

with tabs[1]:
    st.subheader("품절 위험 상품")
    risk = metrics[metrics["상태"].isin([
        "실제재고품절_인기",
        "카페24품절처리_인기",
        "카페24품절_실제재고있음",
        "실제재고없음_판매중위험",
        "긴급품절위험",
        "품절위험",
        "품절주의",
    ])].sort_values(["예상품절일", "7일판매"], ascending=[True, False], na_position="last")
    st.dataframe(risk[show_cols], use_container_width=True, hide_index=True)

with tabs[2]:
    st.subheader("입고 추천")
    inbound = metrics[metrics["추천입고수량"] > 0].sort_values("추천입고수량", ascending=False)
    st.dataframe(inbound[show_cols], use_container_width=True, hide_index=True)
    st.caption("추천입고수량 = (일평균판매 × 거래처 리드타임) + 안전재고 - 셀메이트 기준재고")

with tabs[3]:
    st.subheader("시즌 오픈 추천")
    if season_df.empty:
        st.success("현재 시즌 오픈 추천 상품이 없습니다.")
    else:
        st.dataframe(season_df[show_cols], use_container_width=True, hide_index=True)
        st.markdown("### 바로 쓸 수 있는 MD 액션")
        for _, r in season_df.head(10).iterrows():
            st.info(f"{r['상품명']} · 실제재고 {r['셀메이트재고']}장 → 시즌태그 [{r['시즌태그']}] 기준으로 기획전/메인/릴스 재오픈 추천")

with tabs[4]:
    st.subheader("악성재고 소진 후보")
    dead = metrics[metrics["상태"] == "악성재고후보"].sort_values("기준재고", ascending=False)
    st.dataframe(dead[show_cols], use_container_width=True, hide_index=True)

with tabs[5]:
    st.subheader("전체 상품")
    keyword = st.text_input("상품명 검색")
    filtered = metrics
    if keyword:
        filtered = filtered[filtered["상품명"].astype(str).str.contains(keyword, case=False, na=False)]
    st.dataframe(filtered[show_cols], use_container_width=True, hide_index=True)

with tabs[6]:
    st.subheader("현재 저장된 셀메이트 재고 DB")
    sm_df = db.df("SELECT product_no, product_name, option_name, sellmate_stock, updated_at FROM sellmate_stock ORDER BY updated_at DESC")
    st.dataframe(sm_df, use_container_width=True, hide_index=True)

with tabs[7]:
    st.subheader("최근 저장된 카페24 옵션재고 스냅샷")
    inv_df = db.df("""
        SELECT product_no, option_name, cafe24_stock, cafe24_soldout_status, captured_at
        FROM inventory_snapshots
        WHERE id IN (SELECT MAX(id) FROM inventory_snapshots GROUP BY product_no, option_name)
        ORDER BY product_no, option_name
    """)
    st.dataframe(inv_df, use_container_width=True, hide_index=True)

with tabs[8]:
    st.subheader("알림 로그")
    alert_df = db.df("SELECT alert_type, product_no, severity, message, created_at FROM alerts ORDER BY id DESC")
    st.dataframe(alert_df, use_container_width=True, hide_index=True)
