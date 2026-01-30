"""
🎀 화장품 추천 대시보드 - 메인 앱
"""

import streamlit as st
import pandas as pd
import sys
import os

from utils import css
from utils import scroll
from layouts.sidebar import sidebar

# 컴포넌트 임포트
from components.search_bar import render_search_bar, get_search_text, is_initial_state
from components.product_info import render_product_info
from components.product_analysis import (
    render_top_keywords,
    load_product_analysis_async,
)
from components.product_cards import (
    render_popular_products,
    render_search_results_grid,
    render_recommendations_grid,
)
from components.recommendations import get_recommendations
from components.pagination import (
    calculate_pagination,
    init_page_state,
    check_filter_change,
    get_page_slice,
    render_pagination,
)

# 유틸 임포트
from utils.data_utils import (
    prepare_dataframe,
    get_options,
    apply_filters,
    sort_products,
)

sys.path.append(os.path.dirname(__file__))


# =========================
# ✅ 세션 상태 초기화
# =========================
def init_session_state():
    """세션 상태 초기화"""
    defaults = {
        "product_search": "",
        "search_keyword": "",
        "page": 1,
        "reco_cache": {},
        "reco_target_product_id": None,
        "_skip_scroll_apply_once": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# =========================
# ✅ 스크롤 관련
# =========================
def skip_scroll_apply_once():
    """그래프 UI 조작 시 스크롤 스킵"""
    st.session_state["_skip_scroll_apply_once"] = True


def safe_scroll_to_top():
    """안전하게 스크롤 상단 이동"""
    scroll.request_scroll_to_top()


def apply_scroll():
    """스크롤 적용"""
    if not st.session_state.get("_skip_scroll_apply_once", False):
        scroll.apply_scroll_to_top_if_requested()
    else:
        st.session_state["_skip_scroll_apply_once"] = False


# =========================
# ✅ 콜백 함수들
# =========================
def clear_selected_product():
    """제품 선택 해제"""
    st.session_state["product_search"] = ""
    st.session_state["search_keyword"] = ""
    safe_scroll_to_top()


def select_product_from_reco(product_name: str):
    """추천 상품 클릭 시 선택"""
    st.session_state["product_search"] = product_name
    st.session_state["search_keyword"] = product_name
    safe_scroll_to_top()


# =========================
# ✅ 메인 앱
# =========================
def main():
    # 초기화
    init_session_state()
    st.set_page_config(layout="wide")
    apply_scroll()

    # 데이터 로드
    df = prepare_dataframe()
    _, product_options = get_options(df)

    # 사이드바
    (
        selected_sub_cat,
        selected_skin,
        min_rating,
        max_rating,
        min_price,
        max_price,
    ) = sidebar(df)

    # 메인 타이틀
    st.title("🎀 화장품 추천 대시보드")
    st.markdown("---")

    # 검색창
    selected_product = render_search_bar(product_options, clear_selected_product)
    search_text = get_search_text()
    is_initial = is_initial_state(selected_sub_cat, selected_skin)

    # =========================
    # 인기 상품 TOP 5 (초기 상태)
    # =========================
    if is_initial:
        render_popular_products(df, select_product_from_reco)

    # =========================
    # 제품 상세 정보 (선택 시)
    # =========================
    if selected_product:
        with st.spinner("정보를 불러오는 중입니다..."):
            product_rows = df[df["product_name"] == selected_product]

        if product_rows.empty:
            st.warning("선택한 제품 정보를 찾을 수 없어요.")
        else:
            product_info = product_rows.iloc[0]

            # 제품 기본 정보
            render_product_info(product_info)

            # 대표 키워드
            render_top_keywords(product_info)

            # 대표 리뷰 & 평점 추이 (비동기 로드)
            product_id = product_info.get("product_id", "")
            review_id = product_info.get("representative_review_id_roberta", None)

            container_review = st.empty()
            container_trend = st.empty()

            load_product_analysis_async(
                product_id,
                review_id,
                container_review,
                container_trend,
                skip_scroll_apply_once,
            )

    # =========================
    # 추천/검색 헤더
    # =========================
    sort_option = "추천순"
    if not is_initial:
        if selected_product:
            st.markdown("---")
            st.subheader("👍 이 상품과 유사한 추천 상품")
        else:
            st.subheader("🌟 검색 결과")

        col_1, col_2 = st.columns([7, 3])
        with col_2:
            sort_option = st.selectbox(
                "정렬 옵션",
                options=[
                    "추천순",
                    "평점 높은 순",
                    "리뷰 많은 순",
                    "가격 낮은 순",
                    "가격 높은 순",
                ],
                index=0,
                key="sort_option",
                label_visibility="collapsed",
                on_change=skip_scroll_apply_once,
            )

    # =========================
    # 검색 결과 처리
    # =========================
    if is_initial:
        st.info("왼쪽 사이드바 또는 검색어를 입력하여 상품을 찾아보세요.")
    else:
        # 필터 적용
        filtered_df = apply_filters(
            df,
            selected_sub_cat,
            selected_skin,
            min_rating,
            max_rating,
            min_price,
            max_price,
            search_text,
        )

        # 정렬 적용
        search_df_view = sort_products(filtered_df, sort_option)

        # 페이지네이션 계산
        items_page, total_pages, category_count = calculate_pagination(
            search_df_view, selected_product
        )
        init_page_state(total_pages)

        # 필터 변경 감지
        check_filter_change(
            search_text,
            selected_sub_cat,
            selected_skin,
            min_rating,
            max_rating,
            min_price,
            max_price,
            sort_option,
            safe_scroll_to_top,
        )

        # 페이지 슬라이스
        page_df = get_page_slice(
            search_df_view, selected_product, items_page, category_count
        )

        # =========================
        # 상품 출력
        # =========================
        if not selected_product:
            if page_df.empty:
                st.warning("표시할 상품이 없어요.🥺")
            else:
                render_search_results_grid(
                    page_df,
                    category_count,
                    select_product_from_reco,
                )
        else:
            # 추천 상품 조회 및 출력
            with st.spinner("정보를 불러오는 중입니다..."):
                reco_df_view = get_recommendations(df, selected_product)
            render_recommendations_grid(reco_df_view, select_product_from_reco)

        # =========================
        # 페이지네이션
        # =========================
        show_pagination = selected_product or selected_sub_cat
        if show_pagination and total_pages > 1:
            render_pagination(total_pages, safe_scroll_to_top)

    # CSS 적용
    css.set_css()


if __name__ == "__main__":
    main()
