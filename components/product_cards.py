"""
상품 카드 컴포넌트
- 메인 화면 검색 결과 카드
- 상세 페이지 추천 상품 카드
- 인기 상품 카드
"""

import streamlit as st
import pandas as pd

from utils.data_utils import DEFAULT_IMAGE_URL


def render_popular_product_card(row: pd.Series, index: int, on_select_callback):
    """
    인기 상품 카드 렌더링 (메인 화면 TOP 5용)

    Args:
        row: 상품 정보
        index: 인덱스
        on_select_callback: 선택 버튼 클릭 시 콜백
    """
    with st.container(border=True):
        if row.get("image_url"):
            st.image(row["image_url"], width="stretch", output_format="PNG")

        st.markdown(
            f"""
            <div style="font-size:14px;color:#888;margin-top:4px;min-height:20px;">
            {str(row.get('brand','')) if pd.notna(row.get('brand')) else '&nbsp;'}
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""
            <div style="font-size:13px;font-weight:500;line-height:1.3;margin:2px 0;height:34px;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;">
            {row.get('product_name','')}
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""
            <div style="font-size:14px;font-weight:700;">
                ₩{int(row.get('price',0) or 0):,}
            </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        _, btn_col = st.columns([7, 3], vertical_alignment="center")
        with btn_col:
            st.button(
                "선택",
                key=f"popular_select_{st.session_state.page}_{index}",
                on_click=on_select_callback,
                args=(row.get("product_name", ""),),
                use_container_width=True,
            )


def render_search_result_card(
    row: pd.Series,
    card_key: str,
    on_select_callback,
    image_url: str = DEFAULT_IMAGE_URL,
):
    """
    검색 결과 상품 카드 렌더링 (2열 그리드용)

    Args:
        row: 상품 정보
        card_key: 고유 키
        on_select_callback: 선택 버튼 클릭 시 콜백
        image_url: 이미지 URL (기본값 사용)
    """
    with st.container(border=True):
        col_image, col_info = st.columns([3, 7])

        with col_image:
            st.image(image_url, width=200)

        with col_info:
            badge_html = ""
            if row.get("badge") == "BEST":
                badge_html = "<span style='background:#ffea00;padding:2px 8px;border-radius:8px;font-size:12px;margin-left:8px;'>BEST</span>"
            elif row.get("badge") == "추천":
                badge_html = "<span style='background:#d1f0ff;padding:2px 8px;border-radius:8px;font-size:12px;margin-left:8px;'>추천</span>"

            st.markdown(
                f"""
                <div style="font-size:14px;color:#888;min-height:22px;">
                {str(row.get('brand','')) if pd.notna(row.get('brand')) else '&nbsp;'}
                {badge_html}
                </div>

                <div style="font-size:18px;font-weight:600;margin:4px 0;height:50px;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;line-height:1.3;">
                {row.get('product_name','')}
                </div>

                <div style="font-size:15px;color:#111;font-weight:500;">
                ₩{int(row.get('price',0) or 0):,}
                </div>

                <div style="margin-top:6px;font-size:13px;color:#555;">
                🏷️ 카테고리: {row.get('category_path_norm','')}<br>
                😊 피부 타입: {row.get('skin_type','')}<br>
                ⭐ 평점: {float(row.get('score','') or 0):.2f}<br>
                💬 리뷰 수: {int(row.get('total_reviews',0) or 0):,}
                </div>
                """,
                unsafe_allow_html=True,
            )

            _, btn_col = st.columns([8, 2], vertical_alignment="center")
            with btn_col:
                st.button(
                    "선택",
                    key=card_key,
                    on_click=on_select_callback,
                    args=(row.get("product_name", ""),),
                    use_container_width=True,
                )


def render_recommendation_card(row: pd.Series, on_select_callback):
    """
    추천 상품 카드 렌더링 (3열 그리드용)

    Args:
        row: 상품 정보
        on_select_callback: 선택 버튼 클릭 시 콜백
    """
    with st.container(border=True):
        col_image, col_info = st.columns([3, 7])

        with col_image:
            if row.get("image_url"):
                st.image(row["image_url"], width=180)

        with col_info:
            st.markdown(
                f"""
                <div style="font-size:14px;color:#888;min-height:20px;">
                {str(row.get('brand','')) if pd.notna(row.get('brand')) else '&nbsp;'}
                </div>

                <div style="font-size:18px;font-weight:600;height:50px;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;line-height:1.3;margin:4px 0;">
                {row.get('product_name','')}
                </div>

                <div style="font-size:15px;font-weight:500;">
                ₩{int(row.get('price',0) or 0):,}
                </div>

                <div style="margin-top:6px;font-size:13px;color:#555;">
                🔗 유사도: {float(row.get('similarity',0.0)):.3f}<br>
                ⭐ 추천 점수: {float(row.get('reco_score',0.0)):.3f}
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.button(
                "선택",
                key=f"reco_only_{row.get('product_id','')}",
                on_click=on_select_callback,
                args=(row.get("product_name", ""),),
                use_container_width=True,
            )


def render_popular_products(df: pd.DataFrame, on_select_callback):
    """
    인기 상품 TOP 5 섹션 렌더링

    Args:
        df: 전체 상품 DataFrame
        on_select_callback: 선택 콜백
    """
    st.markdown("## 🔥 인기 상품 TOP 5")

    sort_cols = []
    if "total_reviews" in df.columns:
        sort_cols.append("total_reviews")
    if "score" in df.columns:
        sort_cols.append("score")

    popular_df = (
        df.sort_values(by=sort_cols, ascending=[False] * len(sort_cols))
        .head(5)
        .reset_index(drop=True)
        if sort_cols
        else df.head(5).reset_index(drop=True)
    )

    cols = st.columns(len(popular_df)) if len(popular_df) > 0 else []
    for i, (_, row) in enumerate(popular_df.iterrows()):
        with cols[i]:
            render_popular_product_card(row, i, on_select_callback)

    st.markdown("---")


def render_search_results_grid(
    page_df: pd.DataFrame,
    category_count: int,
    on_select_callback,
):
    """
    검색 결과 그리드 렌더링 (카테고리별 그룹화)

    Args:
        page_df: 페이지 데이터
        category_count: 카테고리 개수
        on_select_callback: 선택 콜백
    """
    if "sub_category" in page_df.columns:
        grouped = page_df.groupby("sub_category", dropna=False)

        # 카테고리별 페이지 상태 초기화
        if "category_pages" not in st.session_state:
            st.session_state["category_pages"] = {}

        for category_name, category_df in grouped:
            _render_category_section(
                category_name,
                category_df,
                category_count,
                on_select_callback,
            )
    else:
        # sub_category 컬럼이 없으면 기존 방식으로 표시
        _render_simple_grid(page_df, on_select_callback)


def _render_category_section(
    category_name,
    category_df: pd.DataFrame,
    category_count: int,
    on_select_callback,
):
    """카테고리 섹션 렌더링"""
    category_display = (
        category_name if pd.notna(category_name) and category_name else "기타"
    )
    st.markdown(f"## 📦 {category_display}")

    if category_count == 1:
        # 카테고리가 1개면 이미 10개씩 페이지네이션 된 상태
        display_count = len(category_df)
        st.markdown(f"*{display_count}개 상품*")
        rows = category_df.reset_index(drop=True)
        current_cat_page = st.session_state.page
        total_cat_pages = 1
    else:
        # 카테고리가 2개 이상이면 각 카테고리별로 6개씩 페이지네이션
        items_per_category = 6

        if category_display not in st.session_state["category_pages"]:
            st.session_state["category_pages"][category_display] = 1

        current_cat_page = st.session_state["category_pages"][category_display]
        total_cat_items = len(category_df)
        total_cat_pages = max(1, -(-total_cat_items // items_per_category))  # ceil

        current_cat_page = min(current_cat_page, total_cat_pages)
        st.session_state["category_pages"][category_display] = current_cat_page

        cat_start = (current_cat_page - 1) * items_per_category
        cat_end = cat_start + items_per_category
        rows = category_df.iloc[cat_start:cat_end].reset_index(drop=True)

        display_count = len(rows)
        st.markdown(
            f"*{cat_start + 1}~{cat_start + display_count} / 총 {total_cat_items}개 상품*"
        )

    # 상품 표시 (2열 그리드)
    for i in range(0, len(rows), 2):
        cols = st.columns(2)
        for j in range(2):
            if i + j < len(rows):
                row = rows.iloc[i + j]
                with cols[j]:
                    render_search_result_card(
                        row,
                        f"cat_{category_display}_{i+j}_{current_cat_page}",
                        on_select_callback,
                    )

    # 카테고리별 페이지네이션 버튼 (카테고리가 2개 이상일 때만)
    if category_count > 1 and total_cat_pages > 1:
        _render_category_pagination(category_display, current_cat_page, total_cat_pages)

    st.markdown("---")


def _render_simple_grid(page_df: pd.DataFrame, on_select_callback):
    """단순 그리드 렌더링 (카테고리 없을 때)"""
    rows = page_df.reset_index(drop=True)
    for i in range(0, len(rows), 2):
        cols = st.columns(2)
        for j in range(2):
            if i + j < len(rows):
                row = rows.iloc[i + j]
                with cols[j]:
                    render_search_result_card(
                        row,
                        f"reco_select_{st.session_state.page}_{i+j}",
                        on_select_callback,
                    )


def _render_category_pagination(
    category_display: str, current_page: int, total_pages: int
):
    """카테고리별 페이지네이션 렌더링"""

    def go_cat_prev(cat_name):
        if st.session_state["category_pages"][cat_name] > 1:
            st.session_state["category_pages"][cat_name] -= 1

    def go_cat_next(cat_name, max_pages):
        if st.session_state["category_pages"][cat_name] < max_pages:
            st.session_state["category_pages"][cat_name] += 1

    col_prev, col_info, col_next = st.columns([1, 2, 1])

    with col_prev:
        st.button(
            "◀ 이전",
            key=f"prev_{category_display}",
            on_click=go_cat_prev,
            args=(category_display,),
            disabled=(current_page == 1),
            use_container_width=True,
        )

    with col_info:
        st.markdown(
            f"<div style='text-align:center; font-weight:bold; padding-top:8px;'>"
            f"{current_page} / {total_pages} 페이지"
            f"</div>",
            unsafe_allow_html=True,
        )

    with col_next:
        st.button(
            "다음 ▶",
            key=f"next_{category_display}",
            on_click=go_cat_next,
            args=(category_display, total_pages),
            disabled=(current_page == total_pages),
            use_container_width=True,
        )


def render_recommendations_grid(reco_df: pd.DataFrame, on_select_callback):
    """
    추천 상품 그리드 렌더링 (3열)

    Args:
        reco_df: 추천 상품 DataFrame
        on_select_callback: 선택 콜백
    """
    if reco_df.empty:
        st.info("추천 가능한 유사 상품이 없어요.😥")
        return

    rows = reco_df.reset_index(drop=True)
    for i in range(0, len(rows), 3):
        cols = st.columns(3)
        for j in range(3):
            if i + j < len(rows):
                row = rows.iloc[i + j]
                with cols[j]:
                    render_recommendation_card(row, on_select_callback)
