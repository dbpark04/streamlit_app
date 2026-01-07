import streamlit as st
import pandas as pd
import math
import random # 임시
import scroll
from sidebar import sidebar, product_filter
from sample_data import load_data
import css

st.set_page_config(layout="wide")

# 요청 시 상단 스크롤 이동 적용
scroll.apply_scroll_to_top_if_requested()



# ===== 데이터프레임 =====
df = load_data()

skin_options = df["skin_type"].unique().tolist()
product_options = df["product"].unique().tolist() 

# ===== 사이드바 =====
selected_sub_cat, selected_skin, min_rating, max_rating = sidebar(df)


# ===== 메인 =====
st.title("화장품 추천 대시보드")
st.subheader("제품명 검색")

search_keyword = st.session_state.get("search_keyword", "") 
def on_search_change(): 
    st.session_state.search_keyword = st.session_state.product_search 

# 제품 선택 해제 버튼
def clear_selected_product():
    # 제품 선택, 검색 상태 초기화
    st.session_state["product_search"] = ""
    st.session_state["search_keyword"] = ""
    scroll.request_scroll_to_top()

# selectbox 컨테이너 안으로 이동
with st.container(border=True):
    col_sel, col_clear = st.columns([10, 1], vertical_alignment="bottom")

    with col_sel:
        selected_product = st.selectbox(
            "제품명을 입력하거나 선택하세요",
            options=[""] + product_options,
            index=0, key="product_search",
            on_change=on_search_change # 제품 선택 시 검색 상태 동기화
        )

    with col_clear:
        # 클릭 시 선택 제품 초기화
        st.button("✕", key="clear_product", help="선택 해제", on_click=clear_selected_product)             

# 추천 상품 클릭
def select_product_from_reco(product_name: str):
    st.session_state["product_search"] = product_name
    st.session_state["search_keyword"] = product_name
    scroll.request_scroll_to_top()

# 검색어로 사용할 값 
search_text = selected_product if selected_product else ""

# 초기 상태 여부
is_initial = (not search_text and not selected_sub_cat and not selected_skin)

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
    # 제품 필터링
    filtered_df = product_filter(df, search_text, selected_sub_cat, selected_skin, min_rating, max_rating)

    # 페이지네이션
    items_page = 6
    total_items = len(filtered_df)
    total_pages = max(1, math.ceil(total_items / items_page))

    # 페이지 초기화
    if "page" not in st.session_state:
        st.session_state.page = 1
    
    st.session_state.page = min(st.session_state.page, total_pages)

    cur_filter = (search_text, tuple(selected_sub_cat), tuple(selected_skin), min_rating, max_rating)

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
        for i, row in page_df.reset_index(drop=True).iterrows():
            # 카드 컨테이너 안에서 버튼, 내용 배치
            with st.container(border=True):

                # 오른쪽 선택 버튼
                top_left, top_right = st.columns([9, 1], vertical_alignment="center")
                with top_right:
                    st.button(
                        "선택",
                        key=f"reco_select_{st.session_state.page}_{i}",
                        on_click=select_product_from_reco,
                        args=(row["product"],),
                    )

                 # 카드형 UI
                col_image, col_info = st.columns([3, 7])

                with col_image:
                    st.image(row["image_url"], width="stretch")

                with col_info:
                    badge_html = ""
                    if row["badge"] == "BEST":
                        badge_html = "<span style='background:#ff4d4f;color:white;padding:2px 8px;border-radius:8px;font-size:12px;margin-left:8px;'>BEST</span>"
                    if row["badge"] == "추천":
                        badge_html = "<span style='background:#1890ff;color:white;padding:2px 8px;border-radius:8px;font-size:12px;margin-left:8px;'>추천</span>"

                    st.markdown(f"""
                        <div style="font-size:14px;color:#888;">
                            {row['brand']}
                            {badge_html}
                        </div>
                        <div style="font-size:18px;font-weight:600;margin:4px 0;">
                            {row['product']}
                        </div>
                        <div style="font-size:15px;color:#111;font-weight:500;">
                            ₩{row['price']:,}
                        </div>
                        <div style="margin-top:6px;font-size:13px;color:#555;">
                            카테고리: {row['main_category']} &gt; {row['sub_category']}<br>
                            피부 타입: {row['skin_type']}<br>
                            대표 키워드: {row['keyword']}<br>
                            추천 점수: {row['score']}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )


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