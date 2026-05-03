# 미샵 재고 관제센터 안정화 최종본

## 이번 버전 핵심 수정
- 셀메이트 CSV에 `product_no`가 없어도 `상품명 정규화 키(product_key)`로 카페24 상품과 매칭합니다.
- 셀메이트 `가용재고`를 실제 기준재고로 사용합니다.
- 카페24 상품 품절/옵션 품절/카페24 재고 0 + 셀메이트 재고 있음 상태를 최우선 감지합니다.
- `invalid_client` 원인 확인을 쉽게 하도록 토큰 연결 테스트/갱신/최초 발급 UI를 분리했습니다.
- Secrets 값 앞뒤 공백을 자동 제거합니다.
- access_token 만료 시 API 요청 중 refresh_token 자동 갱신 후 재시도합니다.
- 상품/옵션재고/주문 조회를 페이지네이션 방식으로 확장했습니다.

## Streamlit Secrets 예시
`.streamlit/secrets.example.toml` 내용을 참고해 Streamlit Cloud Secrets에 입력하세요.

```toml
[app]
db_path = "selleros_inventory.db"

[cafe24]
mall_id = "miyawa"
client_id = "카페24 개발자센터 Client ID"
client_secret = "카페24 개발자센터 Client Secret"
redirect_uri = "https://YOUR-STREAMLIT-APP.streamlit.app"
access_token = ""
refresh_token = ""
api_version = "2026-03-01"
```

## 운영 순서
1. 셀메이트 재고 CSV 업로드
2. `셀메이트 재고 DB 반영`
3. 카페24 `토큰 연결 테스트`
4. 실패 시 `Refresh Token으로 갱신` 또는 `권한 승인 URL`로 최초 발급
5. `카페24 상품/옵션재고/주문 동기화`
6. `카페24 품절 오류` 탭에서 실제재고가 있는데 품절 처리된 상품 확인

## invalid_client가 계속 나올 때
이 오류는 보통 코드 문제가 아니라 아래 중 하나입니다.
- Streamlit Secrets의 `client_secret`이 카페24 개발자센터 앱의 Secret과 다름
- 다른 앱의 Client ID와 Secret을 섞어 넣음
- redirect_uri가 개발자센터에 등록된 값과 완전히 일치하지 않음
- Cafe24 앱 재발급 후 예전 Secret 사용
- refresh_token이 해당 Client ID/Secret으로 발급된 토큰이 아님

이 경우 기존 access_token/refresh_token을 비우고, 같은 Client ID/Secret/redirect_uri 조합으로 권한 승인부터 다시 발급하세요.
