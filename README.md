# 셀러OS 재고관제센터 · MD 재고 레이더

카페24 API와 셀메이트 API를 연동해 쇼핑몰 상품의 재고, 판매상태, 주문 흐름을 자동 수집하고 다음 업무를 알려주는 Streamlit 프로그램입니다.

- 품절 위험 상품
- 이미 품절된 인기상품
- 입고 추천 상품
- 시즌 오픈 추천 상품
- 악성재고 소진 후보

## 1. 빠른 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

처음 실행하면 샘플 데이터로 대시보드를 확인할 수 있습니다.

## 2. Streamlit Cloud 배포

1. 이 폴더 전체를 GitHub 새 레포에 업로드합니다.
2. Streamlit Cloud에서 New app을 선택합니다.
3. `app.py`를 실행 파일로 지정합니다.
4. Secrets에 `.streamlit/secrets.toml.example` 내용을 복사해 붙여넣습니다.
5. 카페24 개발자센터에서 받은 값으로 `mall_id`, `client_id`, `client_secret`, `redirect_uri`를 수정합니다.

## 3. 카페24 API 설정 순서

카페24 Admin API는 쇼핑몰 관리자가 쇼핑몰 전반의 상품, 주문, 회원, 게시판 등의 정보를 조회·생성·수정·삭제할 때 쓰는 OAuth 2.0 기반 REST API입니다.

### 3-1. 앱 생성

1. 카페24 개발자센터 접속
2. 앱 생성
3. Redirect URI 등록
   - 로컬 테스트: `http://localhost:8501`
   - Streamlit Cloud: `https://앱주소.streamlit.app`
4. Client ID / Client Secret 확인

### 3-2. 필요한 권한

초기 MVP 기준 권장 권한:

- 상품 조회: `mall.read_product`
- 주문 조회: `mall.read_order`

추후 판매상태 변경, 진열상태 변경, 상품 수정까지 하려면 write 권한을 별도로 추가합니다.

### 3-3. 토큰 발급

1. 앱 왼쪽 사이드바의 `카페24 권한 승인 URL 열기` 클릭
2. 카페24 로그인/승인
3. Redirect URI로 돌아온 주소에서 `code=` 뒤 값을 복사
4. 앱의 `승인 후 code 붙여넣기`에 입력
5. `Access Token 발급` 클릭
6. 나온 `access_token`, `refresh_token`을 Streamlit Secrets에 저장

## 4. 셀메이트 API 연결

셀메이트는 API를 통한 외부 시스템 연동을 지원합니다. 다만 실제 endpoint와 인증 방식은 API 신청 후 제공받는 문서 기준으로 맞춰야 합니다.

현재 레포에는 `src/sellmate_client.py`에 어댑터 구조만 만들어져 있습니다.

API 문서를 받으면 아래 데이터를 연결하면 됩니다.

- 상품별 실제 물류재고
- 입고 수량
- 출고 수량
- 반품 입고 수량
- 배송/송장 상태

## 5. 프로그램 판단 기준

### 품절 위험

```text
예상품절일 = 현재재고 / 최근 7~14일 기준 일평균판매량
```

- 1일 이내: 긴급품절위험
- 3일 이내: 품절위험
- 7일 이내: 품절주의

### 입고 추천

```text
추천입고수량 = (일평균판매 × 거래처 리드타임) + 안전재고 - 현재재고
```

### 시즌 오픈 추천

조건:

- 현재 월의 시즌 태그와 상품 태그가 일치
- 재고 10장 이상
- 미진열이거나 최근 7일 판매가 2장 이하

시즌 태그 규칙은 `src/season_rules.py`에서 수정합니다.

### 악성재고 후보

조건:

- 재고 30장 이상
- 최근 30일 판매 3장 이하

## 6. 파일 구조

```text
selleros_inventory_radar/
├─ app.py
├─ requirements.txt
├─ README.md
├─ .streamlit/
│  └─ secrets.toml.example
└─ src/
   ├─ db.py
   ├─ cafe24_client.py
   ├─ sellmate_client.py
   ├─ analytics.py
   ├─ season_rules.py
   ├─ sample_data.py
   └─ utils.py
```

## 7. 다음 개발 작업

1. 카페24 옵션별 재고 endpoint 확인 후 옵션 단위 재고 수집 강화
2. 주문 취소/반품 상태를 주문수 계산에서 제외
3. 셀메이트 실제 API 연결
4. 처리완료, 입고요청, 세일요청 업무 버튼 추가
5. 셀러OS 기존 메뉴에 `운영관리 > 재고관제센터`로 삽입
6. 마케팅 OS와 연결해 악성재고 세일 문구와 시즌 재오픈 카피 자동 생성
