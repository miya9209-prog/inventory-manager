# 재고 관제센터

## v2 변경사항
- 셀메이트 CSV 인코딩 오류 수정: cp949/euc-kr 자동 인식
- 업로드 파일 예시: stk_stockList_20260502_001341.csv
- 셀메이트 파일에 상품코드가 없어도 상품명 기준 임시 매칭 가능
- 가용재고 컬럼을 우선 재고로 인식
- 카페24 인증 버튼을 '최초 인증' 영역으로 숨김
- 실제 운영 시에는 '카페24 상품/주문 동기화'만 사용

## 운영 흐름
1. 셀메이트 재고 파일 업로드
2. 셀메이트 재고 DB 업데이트
3. 카페24 상품/주문 동기화
4. 긴급 알림/품절 위험/입고 추천 확인


## v3
- 셀메이트 CSV CP949/EUC-KR 인코딩 처리 강화
- utf-8 decode 오류 수정


## 풀버전 운영 기준
- 셀메이트 CSV/엑셀 직접 업로드
- CP949/EUC-KR CSV 자동 인식
- 셀메이트 가용재고 기준 DB 업데이트
- 카페24 상품/주문 동기화
- 카페24 옵션 재고 합산 구조 포함
- 품절위험, 입고추천, 시즌오픈추천, 악성재고 판단
- 알림 로그 확장 가능


## 2026-05 OAuth 토큰 발급 수정 반영
- 카페24 승인 후 URL에 붙어 돌아오는 `code`를 앱에서 자동 감지합니다.
- Access Token 발급 시 Cafe24 OAuth 요구 방식에 맞춰 Basic Auth 헤더를 사용합니다.
- 카페24 개발자센터 Redirect URI는 아래 하나만 등록하세요.

```text
https://ms-inventory-manager.streamlit.app/oauth
```

## 적용 후 필수 작업
1. GitHub에 전체 덮어쓰기
2. Streamlit Clear cache
3. Streamlit Reboot app
4. 카페24 권한 승인 URL 열기
5. 돌아온 code 자동 감지 확인
6. Access Token 발급 클릭
7. 발급된 access_token / refresh_token을 Streamlit Secrets에 저장
