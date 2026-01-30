"""
페이지네이션 컴포넌트
"""

import streamlit as st
import math


def calculate_pagination(
    search_df: "pd.DataFrame",
    selected_product: str,
) -> tuple:
    """
    페이지네이션 계산

    Args:
        search_df: 검색 결과 DataFrame
        selected_product: 선택된 제품명

    Returns:
        (items_page, total_pages, category_count)
    """
    # 카테고리 개수 확인
    if "sub_category" in search_df.columns:
        grouped = search_df.groupby("sub_category", dropna=False)
        category_count = len(grouped)
    else:
        category_count = 1

    # 카테고리가 1개면 10개씩, 2개 이상이면 전체 데이터
    if category_count == 1:
        items_page = 10
    else:
        items_page = max(1, len(search_df))

    total_items = len(search_df)
    total_pages = max(1, math.ceil(total_items / items_page))

    return items_page, total_pages, category_count


def init_page_state(total_pages: int):
    """페이지 상태 초기화"""
    if "page" not in st.session_state:
        st.session_state.page = 1
    st.session_state.page = min(st.session_state.page, total_pages)


def check_filter_change(
    search_text: str,
    selected_sub_cat: list,
    selected_skin: list,
    min_rating: float,
    max_rating: float,
    min_price: int,
    max_price: int,
    sort_option: str,
    scroll_to_top_callback,
):
    """필터 변경 감지 및 페이지 리셋"""
    cur_filter = (
        search_text,
        tuple(selected_sub_cat),
        tuple(selected_skin),
        min_rating,
        max_rating,
        min_price,
        max_price,
        sort_option,
    )
    if st.session_state.get("prev_filter") != cur_filter:
        st.session_state.page = 1
        st.session_state.prev_filter = cur_filter
        scroll_to_top_callback()


def get_page_slice(
    search_df: "pd.DataFrame",
    selected_product: str,
    items_page: int,
    category_count: int,
) -> "pd.DataFrame":
    """
    현재 페이지에 해당하는 데이터 슬라이스 반환

    Args:
        search_df: 검색 결과 DataFrame
        selected_product: 선택된 제품명
        items_page: 페이지당 아이템 수
        category_count: 카테고리 개수

    Returns:
        페이지 데이터 DataFrame
    """
    import pandas as pd

    if selected_product:
        return pd.DataFrame()

    start = (st.session_state.page - 1) * items_page
    end = start + items_page

    if category_count == 1:
        return search_df.iloc[start:end]
    else:
        return search_df


def render_pagination(total_pages: int, scroll_to_top_callback):
    """
    페이지네이션 UI 렌더링

    Args:
        total_pages: 전체 페이지 수
        scroll_to_top_callback: 스크롤 콜백
    """
    if total_pages <= 1:
        return

    st.markdown("---")
    col_prev, col_info, col_next = st.columns([1, 2, 1])

    def go_prev():
        if st.session_state.page > 1:
            st.session_state.page -= 1
            scroll_to_top_callback()

    def go_next():
        if st.session_state.page < total_pages:
            st.session_state.page += 1
            scroll_to_top_callback()

    with col_prev:
        st.button("이전", key="prev_page", on_click=go_prev)

    with col_next:
        st.button("다음", key="next_page", on_click=go_next)

    with col_info:
        st.markdown(
            f"<div style='text-align:center; font-weight:bold;'>"
            f"{st.session_state.page} / {total_pages} 페이지"
            f"</div>",
            unsafe_allow_html=True,
        )
