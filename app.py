import streamlit as st
import pandas as pd
from src.db import DB
from src.sample_data import seed
from src.cafe24_client import Cafe24Client
from src.sellmate_client import SellmateClient
from src.analytics import build_product_metrics, classify, season_open_candidates, generate_alerts
from src.utils import get_secret

st.set_page_config(page_title="셀러OS 재고관제센터", page_icon="📦", layout="wide")

DB_PATH = get_secret("app", "db_path", "selleros_inventory.db")
USE_SAMPLE = bool(get_secret("app", "use_sample_data", True))
db = DB(DB_PATH)

st.title("📦 셀러OS 재고관제센터 · MD 재고 레이더")
st.caption("카페24 + 셀메이트 데이터를 기반으로 품절위험, 입고추천, 시즌오픈추천, 악성재고를 자동 분류합니다.")

with st.sidebar:
    st.header("설정")
    mode = st.radio("데이터 모드", ["샘플 데이터", "카페24 API 연동"], index=0 if USE_SAMPLE else 1)
    if st.button("샘플 데이터 새로 넣기"):
        seed(db)
        st.success("샘플 데이터가 입력되었습니다.")
        st.rerun()
    st.divider()
    st.subheader("카페24 인증")
    mall_id = get_secret("cafe24", "mall_id")
    client_id = get_secret("cafe24", "client_id")
    client_secret = get_secret("cafe24", "client_secret")
    redirect_uri = get_secret("cafe24", "redirect_uri")
    access_token = get_secret("cafe24", "access_token")
    refresh_token = get_secret("cafe24", "refresh_token")
    api_version = get_secret("cafe24", "api_version", "2025-12-01")
    cafe = Cafe24Client(mall_id, client_id, client_secret, redirect_uri, access_token, refresh_token, api_version)
    scopes = ["mall.read_product", "mall.read_order"]
    if mall_id and client_id and redirect_uri:
        st.link_button("카페24 권한 승인 URL 열기", cafe.auth_url(scopes))
    code = st.text_input("승인 후 code 붙여넣기", type="password")
    if st.button("Access Token 발급") and code:
        try:
            token = cafe.exchange_code(code)
            st.success("토큰 발급 성공. 아래 값을 Secrets에 저장하세요.")
            st.json(token)
        except Exception as e:
            st.error(f"토큰 발급 실패: {e}")
    if st.button("카페24 상품/주문 동기화"):
        try:
            products_payload = cafe.fetch_products(limit=100)
            rows, inv = cafe.normalize_products(products_payload)
            db.upsert_products(rows)
            db.insert_inventory_snapshots(inv)
            orders_payload = cafe.fetch_orders(days=14, limit=100)
            sales = cafe.normalize_orders(orders_payload)
            if sales:
                db.upsert_sales_daily(sales)
            st.success(f"동기화 완료: 상품 {len(rows)}개, 주문일별 {len(sales)}건")
        except Exception as e:
            st.error(f"동기화 실패: {e}")
    st.divider()
    st.subheader("셀메이트")
    sm = SellmateClient(get_secret("sellmate", "base_url"), get_secret("sellmate", "api_key"), get_secret("sellmate", "api_secret"))
    st.caption("셀메이트 API 문서 수령 후 endpoint를 src/sellmate_client.py에 맞추면 됩니다.")

if mode == "샘플 데이터":
    # DB가 비어 있으면 자동 seed
    if db.df("SELECT COUNT(*) AS cnt FROM products").iloc[0].cnt == 0:
        seed(db)

metrics = classify(build_product_metrics(db))
season_df = season_open_candidates(metrics)
alerts = generate_alerts(metrics, season_df)
db.replace_alerts(alerts)

if metrics.empty:
    st.warning("아직 데이터가 없습니다. 샘플 데이터를 넣거나 카페24 API 동기화를 실행하세요.")
    st.stop()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("이미 품절된 인기상품", int((metrics["상태"] == "이미품절_인기").sum()))
c2.metric("3일 내 품절위험", int(metrics["상태"].isin(["긴급품절위험", "품절위험"]).sum()))
c3.metric("7일 내 품절주의", int((metrics["상태"] == "품절주의").sum()))
c4.metric("시즌 오픈 추천", len(season_df))
c5.metric("악성재고 후보", int((metrics["상태"] == "악성재고후보").sum()))

st.divider()

tabs = st.tabs(["오늘의 긴급 알림", "품절 위험", "입고 추천", "시즌 오픈 추천", "악성재고 소진", "전체 상품"])

show_cols = ["product_no", "상품명", "카테고리", "재고", "3일판매", "7일판매", "14일판매", "예상품절일", "추천입고수량", "진열", "판매", "품절", "상태", "시즌태그"]

with tabs[0]:
    st.subheader("오늘 MD가 먼저 봐야 할 상품")
    urgent = metrics[metrics["상태"].isin(["이미품절_인기", "긴급품절위험", "품절위험"])]
    if urgent.empty:
        st.success("긴급 품절/입고 알림이 없습니다.")
    else:
        st.dataframe(urgent[show_cols], use_container_width=True, hide_index=True)

with tabs[1]:
    st.subheader("품절 위험 상품")
    risk = metrics[metrics["상태"].isin(["이미품절_인기", "긴급품절위험", "품절위험", "품절주의"])].sort_values(["예상품절일", "7일판매"], ascending=[True, False], na_position="last")
    st.dataframe(risk[show_cols], use_container_width=True, hide_index=True)

with tabs[2]:
    st.subheader("입고 추천")
    inbound = metrics[metrics["추천입고수량"] > 0].sort_values("추천입고수량", ascending=False)
    st.dataframe(inbound[show_cols], use_container_width=True, hide_index=True)
    st.caption("추천입고수량 = (일평균판매 × 거래처 리드타임) + 안전재고 - 현재재고")

with tabs[3]:
    st.subheader("시즌 오픈 추천")
    st.write("재고는 있는데 현재 시즌 키워드와 맞고, 진열이 약하거나 최근 판매가 낮은 상품입니다.")
    if season_df.empty:
        st.success("현재 시즌 오픈 추천 상품이 없습니다.")
    else:
        st.dataframe(season_df[show_cols], use_container_width=True, hide_index=True)
        st.markdown("### 바로 쓸 수 있는 MD 액션")
        for _, r in season_df.head(8).iterrows():
            st.info(f"{r['상품명']} · 재고 {r['재고']}장 → 시즌태그 [{r['시즌태그']}] 기준으로 기획전/메인/릴스 재오픈 추천")

with tabs[4]:
    st.subheader("악성재고 소진 후보")
    dead = metrics[metrics["상태"] == "악성재고후보"].sort_values("재고", ascending=False)
    st.dataframe(dead[show_cols], use_container_width=True, hide_index=True)
    st.caption("기준: 재고 30장 이상 + 최근 30일 판매 3장 이하")

with tabs[5]:
    st.subheader("전체 상품")
    keyword = st.text_input("상품명 검색")
    filtered = metrics
    if keyword:
        filtered = filtered[filtered["상품명"].str.contains(keyword, case=False, na=False)]
    st.dataframe(filtered[show_cols], use_container_width=True, hide_index=True)

st.divider()
st.markdown("""
### 다음 개발 포인트
1. 카페24 상품 옵션별 재고 endpoint에 맞춰 옵션 단위 재고를 세분화합니다.  
2. 셀메이트 API 문서를 받은 뒤 실제 물류재고, 입고, 출고, 반품 데이터를 `src/sellmate_client.py`에 연결합니다.  
3. 처리완료/입고요청/세일요청 버튼을 추가해 업무 상태까지 관리합니다.
""")
