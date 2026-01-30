"""
검색창 컴포넌트
"""

import streamlit as st


def render_search_bar(product_options: list, on_clear_callback):
    """
    검색창 렌더링

    Args:
        product_options: 제품명 자동완성 옵션 목록
        on_clear_callback: 초기화 버튼 클릭 시 콜백

    Returns:
        selected_product: 선택된 제품명
    """
    with st.container(border=True):
        col_text, col_sel, col_clear = st.columns(
            [5, 5, 1], vertical_alignment="bottom"
        )

        with col_text:
            st.text_input(
                "🗝️키워드 검색",
                placeholder="예: 수분, 촉촉, 진정",
                key="search_keyword",
            )

        with col_sel:
            st.selectbox(
                "🔎 제품명 검색",
                options=[""] + product_options,
                key="product_search",
            )
            selected_product = st.session_state.get("product_search", "")

        with col_clear:
            st.button(
                "✕",
                help="검색 초기화",
                on_click=on_clear_callback,
            )

    return selected_product


def get_search_text() -> str:
    """현재 검색어 반환"""
    if st.session_state.get("product_search"):
        return st.session_state.product_search
    return st.session_state.get("search_keyword", "").strip()


def is_initial_state(selected_sub_cat: list, selected_skin: list) -> bool:
    """초기 상태인지 확인"""
    search_text = get_search_text()
    return not search_text and not selected_sub_cat and not selected_skin
