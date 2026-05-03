# 재고 관제센터 전체 완성본

## 포함 기능
- 셀메이트 CSV/엑셀 직접 업로드
- CP949/EUC-KR CSV 자동 인식
- 셀메이트 가용재고 기준 DB 업데이트
- 카페24 OAuth code 자동 감지
- 카페24 Access Token 발급
- 카페24 상품/주문/옵션재고 동기화
- options API 우선 조회, variants API fallback
- 카페24 옵션 재고 합산
- 셀메이트 실제재고 vs 카페24 재고/품절상태 비교
- 품절위험, 입고추천, 시즌오픈추천, 악성재고 판단
- 카페24 옵션재고 스냅샷 확인 탭
- 알림 로그 탭

## Streamlit Secrets 예시
```toml
[app]
db_path = "selleros_inventory.db"
use_sample_data = true

[cafe24]
mall_id = "miyawa"
client_id = "카페24 Client ID"
client_secret = "카페24 Client Secret"
redirect_uri = "https://ms-inventory-manager.streamlit.app/oauth"
access_token = ""
refresh_token = ""
api_version = "2026-03-01"
```

## 운영 순서
1. 셀메이트 재고 파일 업로드
2. 셀메이트 재고 DB 업데이트
3. 카페24 상품/주문/옵션재고 동기화
4. 긴급 알림/품절 위험/입고 추천 확인
