import streamlit as st
import pandas as pd
import math
import random # 임시
import scroll
from sidebar_filters import render_rating_slider, filter_by_rating
import css

st.set_page_config(layout="wide")

# 페이지 최상단 앵커
scroll.apply_scroll_to_top_if_requested()

# ===== 임시 테스트용 데이터 =====
products = [
    # 크림
    "닥터알파 수분 장벽 크림",
    "라포레 진정 시카 크림",
    "더마큐어 세라마이드 크림",
    "하이드라랩 딥모이스트 크림",
    "바이오힐 보습 리페어 크림",
    "에스트라 아토베리어 크림",
    "라운드랩 자작나무 수분크림",
    "피지오겔 데일리 모이스처 크림",

    # 토너
    "라운드랩 독도 토너",
    "아누아 어성초 77 토너",
    "닥터지 그린 마일드 토너",
    "마녀공장 비피다 토너",
    "아이오페 더마 리페어 토너",
    "에스트라 아토베리어 토너",

    # 에센스/세럼
    "마녀공장 갈락토미 에센스",
    "아이오페 비타민 C 세럼",
    "이니스프리 그린티 씨드 세럼",
    "토리든 다이브인 저분자 세럼",
    "닥터지 레드 블레미쉬 앰플",
    "라로슈포제 히알루 B5 세럼",

    # 클렌저
    "라운드랩 약산성 클렌징폼",
    "닥터지 그린 딥 포밍 클렌저",
    "에스트라 약산성 클렌저",
    "토리든 밸런스 클렌징 폼",
    "마녀공장 퓨어 클렌징 오일",
    "센텔리안24 마데카 클렌저",
]

categories = {
    "크림": ["보습", "장벽강화", "진정"],
    "토너": ["수분공급", "피부결정돈", "진정"],
    "에센스": ["광채", "미백", "탄력"],
    "세럼": ["미백", "주름개선", "보습"],
    "클렌저": ["세정", "저자극", "피지관리"],
}

skin_types = ["건성", "지성", "복합성", "민감성"]

@st.cache_data
def load_data():
    rows = []

    for product in products:
        if "크림" in product:
            category = "크림"
        elif "토너" in product:
            category = "토너"
        elif "에센스" in product or "앰플" in product or "세럼" in product:
            category = random.choice(["에센스", "세럼"])
        else:
            category = "클렌저"

        rows.append({
            "product": product,
            "category": category,
            "skin_type": random.choice(skin_types),
            "keyword": random.choice(categories[category]),
            "score": round(random.uniform(1.0, 5.0), 2)
        })

    return pd.DataFrame(rows)

df = load_data()



# ===== 사이드바 =====
st.sidebar.header("검색 조건")

cat_options = df["category"].unique().tolist()
skin_options = df["skin_type"].unique().tolist()

st.sidebar.subheader("카테고리")

selected_cat = []
for cat in df["category"].unique():
    if st.sidebar.checkbox(cat, key=f"cat_{cat}"):
        selected_cat.append(cat)

st.sidebar.subheader("피부 타입")

selected_skin = []
for skin in df["skin_type"].unique():
    if st.sidebar.checkbox(skin, key=f"skin_{skin}"):
        selected_skin.append(skin)

# 평점 슬라이더 (최소, 최대)
min_rating, max_rating = render_rating_slider()


# ===== 메인 =====
st.title("화장품 추천 대시보드")
st.subheader("제품명 검색")

search_keyword = st.session_state.get("search_keyword", "") 
def on_search_change(): 
    st.session_state.search_keyword = st.session_state.product_search 

product_options = df["product"].unique().tolist() 

selected_product = st.selectbox("제품명을 입력하거나 선택하세요", options=[""] + product_options, index=0, key="product_search", on_change=on_search_change) 

# 검색어로 사용할 값 
search_text = selected_product if selected_product else ""

# 초기 상태 여부
is_initial = (not search_text and not selected_cat and not selected_skin)

# 제품 정보
if selected_product:
    product_info = df[df["product"] == selected_product].iloc[0]
    
    st.subheader("선택한 제품 정보")
    col1, col2, col3 = st.columns(3)

    col1.metric("제품명", product_info["product"])
    col2.metric("대표 키워드", product_info["keyword"])
    col3.metric("피부 타입", product_info["skin_type"])



# ===== 추천 페이지 =====
st.subheader("추천 상품")

if is_initial:
    st.info("왼쪽 사이드바 또는 검색어를 입력하여 상품을 찾아보세요.")
else:
    filtered_df = df.copy()

    # 검색어 조건
    if search_text is not None:
        filtered_df = filtered_df[filtered_df["product"].str.contains(search_text, case=False)]

    # 카테고리 필터
    if selected_cat:
        filtered_df = filtered_df[filtered_df["category"].isin(selected_cat)]

    # 피부 타입 필터
    if selected_skin:
        filtered_df = filtered_df[filtered_df["skin_type"].isin(selected_skin)]
        
    # 평점 필터
    filtered_df = filter_by_rating(filtered_df, min_rating, max_rating)

    # 평점 기준 정렬
    filtered_df = filtered_df.sort_values(by="score", ascending=False)

    # 페이지네이션
    items_page = 6
    total_items = len(filtered_df)
    total_pages = max(1, math.ceil(total_items / items_page))

    # 페이지 초기화
    if "page" not in st.session_state:
        st.session_state.page = 1
    
    st.session_state.page = min(st.session_state.page, total_pages)

    cur_filter = (search_text, tuple(selected_cat), tuple(selected_skin), min_rating, max_rating)

    # 검색어/필터 변경시
    if st.session_state.get("prev_filter") != cur_filter:
        st.session_state.page = 1
        st.session_state.prev_filter = cur_filter
        # 필터 변경 시에도 상단으로 이동
        scroll.request_scroll_to_top()

    # 데이터 슬라이싱
    start = (st.session_state.page - 1) * items_page
    end = start + items_page
    page_df = filtered_df.iloc[start:end]

    # 추천 상품 출력
    if page_df.empty:
        st.warning("조건에 맞는 상품이 없습니다.")
    else:
        for _, row in page_df.iterrows():
            st.markdown(f"""
                        **{row['product']}**
                        - 카테고리: {row['category']}
                        - 피부 타입: {row['skin_type']}
                        - 대표 키워드: {row['keyword']}
                        - 평점: {row['score']}
                        """)
            st.divider()

    # 페이지 이동 버튼
    st.markdown("---")

    col_prev, col_info, col_next = st.columns([1, 2, 1])

    # 이전 페이지 이동 콜백 함수
    def go_prev():
        if st.session_state.page > 1:
            st.session_state.page -= 1
            scroll.request_scroll_to_top() 


    # 다음 페이지 이동 콜백 함수
    def go_next():
        if st.session_state.page < total_pages:
            st.session_state.page += 1
            scroll.request_scroll_to_top() 


    with col_prev:
        # on_click 콜백 방식으로 변경
        st.button("이전", key="prev_page", on_click=go_prev)  # (수정)

    with col_next:
        # on_click 콜백 방식으로 변경
        st.button("다음", key="next_page", on_click=go_next)  # (수정)

    with col_info:
        st.markdown(
            f"<div style='text-align:center; font-weight:bold;'>"
            f"{st.session_state.page} / {total_pages} 페이지"
            f"</div>",
            unsafe_allow_html=True
        )

css.set_css()