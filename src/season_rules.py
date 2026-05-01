from datetime import date

MONTH_TAGS = {
    1: ["겨울", "기모", "울", "니트", "아우터", "명절룩"],
    2: ["봄준비", "간절기", "니트", "자켓", "입학식", "하객룩"],
    3: ["봄", "간절기", "자켓", "셔츠", "블라우스", "출근룩"],
    4: ["봄", "가정의달", "모임룩", "자켓", "블라우스", "셔츠"],
    5: ["가정의달", "모임룩", "여름니트", "린넨", "조끼", "살안타템"],
    6: ["여름", "린넨", "시어서커", "쿨링", "살안타템", "장마템"],
    7: ["한여름", "휴가룩", "원피스", "쿨링", "장마템", "시어서커"],
    8: ["늦여름", "휴가룩", "쿨링", "간절기준비", "셔츠"],
    9: ["가을", "간절기", "자켓", "셔츠", "슬랙스", "출근룩"],
    10: ["가을", "니트", "자켓", "하객룩", "모임룩", "슬랙스"],
    11: ["초겨울", "니트", "아우터", "코트", "기모", "모임룩"],
    12: ["겨울", "기모", "울", "아우터", "연말룩", "모임룩"],
}

CATEGORY_HINTS = {
    "조끼": ["조끼", "베스트", "레이어드"],
    "여름니트": ["린넨", "쿨", "매쉬", "네트", "스카시", "니트"],
    "장마템": ["점퍼", "바람막이", "후드", "시어서커"],
    "모임룩": ["블라우스", "자켓", "원피스", "가디건"],
    "출근룩": ["셔츠", "슬랙스", "자켓", "블라우스"],
}

def current_season_tags(month: int | None = None):
    m = month or date.today().month
    return MONTH_TAGS.get(m, [])

def infer_tags(product_name: str, category: str = "", month: int | None = None):
    text = f"{product_name} {category}".lower()
    tags = set(current_season_tags(month))
    for tag, hints in CATEGORY_HINTS.items():
        if any(h.lower() in text for h in hints):
            tags.add(tag)
    return ",".join(sorted(tags))
