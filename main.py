import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import math
import css
import sys
import os
import re
import scroll
from load_data import load_raw_df, make_df, load_reviews, load_date_score, rating_trend
from sidebar import sidebar, product_filter
from pathlib import Path

st.cache_data.clear()

if "product_search" not in st.session_state:
    st.session_state["product_search"] = ""
if "search_keyword" not in st.session_state:
    st.session_state["search_keyword"] = ""

sys.path.append(os.path.dirname(__file__))

st.set_page_config(layout="wide")

# 요청 시 상단 스크롤 이동 적용
scroll.apply_scroll_to_top_if_requested()

# ===== parquet 로딩 =====
base_dir = Path(__file__).resolve().parent
PRODUCTS_BASE_DIR = base_dir / "data" / "integrated_products_final"
REVIEWS_BASE_DIR = base_dir / "data" / "partitioned_reviews"

product_df = load_raw_df(PRODUCTS_BASE_DIR)
df = make_df(product_df)

skin_options = df["skin_type"].unique().tolist()
product_options = df["product_name"].unique().tolist()

# ===== 사이드바 =====
selected_sub_cat, selected_skin, min_rating, max_rating, min_price, max_price = sidebar(df)

# ===== 메인 =====
st.title("화장품 추천 대시보드")
st.markdown("---")

search_keyword = st.session_state.get("search_keyword", "")


def on_search_change():
    if "product_search" in st.session_state:
        st.session_state["search_keyword"] = st.session_state["product_search"]


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
            index=0,
            key="product_search",
            on_change=on_search_change,  # 제품 선택 시 검색 상태 동기화
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

# ===== 인기상품 TOP 5 (리뷰 수, 평점 ) =====
if is_initial:
    st.markdown("## 인기 상품 TOP 5")

    popular_df = (
        df.sort_values(
            by=["total_reviews", "score"],
            ascending=[False, False]
        )
        .head(5)
        .reset_index(drop=True)
    )

    for i, row in popular_df.iterrows():
        col_info, col_btn = st.columns([8, 2])

        with col_info:
            st.markdown(
                f"""
                **{row['product_name']}**  
                평점: {row['score']} | 리뷰 수: {int(row['total_reviews']):,}
                """
            )

        with col_btn:
            st.button(
                "선택",
                key=f"popular_select_{i}",
                on_click=select_product_from_reco,
                args=(row["product_name"],),
                use_container_width=True,
            )

    st.markdown("---")


# 제품 정보
if selected_product:
    product_info = df[df["product_name"] == selected_product].iloc[0]

    st.subheader("선택한 제품 정보")
    col1, col2, col3 = st.columns(3)

    col1.metric("제품명", product_info["product_name"])
    col2.metric("브랜드", product_info.get("brand", ""))
    col3.metric("피부 타입", product_info.get("skin_type", ""))

    col4, col5, col6 = st.columns(3)
    col4.metric("가격", f"₩{int(product_info.get('price', 0)):,}")
    col5.metric("리뷰 수", f"{int(product_info.get('total_reviews', 0)):,}")
    col6.metric("카테고리", product_info.get("sub_category", ""))

    if product_info.get("product_url"):
        st.link_button("상품 페이지", product_info["product_url"])

    # 대표 키워드
    st.markdown("### 대표 키워드")
    top_kw = product_info.get("top_keywords", "")
    if isinstance(top_kw, (list, np.ndarray)):
        top_kw = ", ".join(map(str, top_kw))
    st.write(top_kw if top_kw else "-")

    sub_cat = product_info.get("sub_category", "")

    # 대표 리뷰
    if selected_product:
        product_info = df[df["product_name"] == selected_product].iloc[0]
        product_id = product_info["product_id"]
        review_id = product_info["representative_review_id"]
        category = product_info["category"]
        
        text = load_reviews(product_id, review_id, category, REVIEWS_BASE_DIR)

    st.markdown("### 대표 리뷰")

    if not text:
        st.info("대표 리뷰가 없습니다.")
    else:
        st.text(text)

    # 평점 추이 그래프
    if selected_product:
        product_info = df[df["product_name"] == selected_product].iloc[0]
        product_id = product_info["product_id"]
        category = product_info["category"]
        
        review_df = load_date_score(product_id, category, REVIEWS_BASE_DIR)

    st.markdown("### 평점 추이")
    col_left, col_mid, col_right, col_empty = st.columns([1, 1, 1, 1])

    # 집계 기준
    with col_left:
        freq_label = st.selectbox("평균 기준", ["일간", "주간", "월간"], index=1)

    freq_map = {"일간": ("D", 7), "주간": ("W", 4), "월간": ("M", 3)}
    freq, ma_window = freq_map[freq_label]

    with col_mid:
        min_date = review_df["date"].min().date()
        max_date = review_df["date"].max().date()
        
        date_range = st.date_input("기간 선택", value=(min_date, max_date), min_value=min_date, max_value=max_date)

    DATE_RANGE_KEY = "rating_date_range"

    with col_right:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("↺", key="reset_date", help="날짜 초기화"):
            st.session_state[DATE_RANGE_KEY] = (min_date, max_date)

    trend_df = pd.DataFrame()
    is_date_range_ready = False

    if isinstance(date_range, tuple) and len(date_range) == 2:
        is_date_range_ready = True
        start_date, end_date = date_range
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)

        date_df = review_df.loc[(review_df["date"] >= start_date) & (review_df["date"] <= end_date)]

        if not date_df.empty:
            trend_df = rating_trend(date_df, freq=freq, ma_window=ma_window)

    else:
        st.info("마지막 날짜를 선택해주세요.")
        date_df = pd.DataFrame()    # 그래프 비활성화

    if not is_date_range_ready:
        pass

    elif trend_df.empty:
        st.info("선택한 기간에 대한 평점 데이터가 없습니다.")

    else:
        fig = go.Figure()

        # 주간 평균
        fig.add_trace(go.Scatter(
            x=trend_df["date"], 
            y=trend_df["avg_score"], 
            mode="lines", 
            name=f"{freq_label} 평균", 
            line=dict(color="slateblue", width=2, dash="dot"), 
            opacity=0.4
            ))
        
        # 이동 평균
        fig.add_trace(go.Scatter(
            x=trend_df["date"], 
            y=trend_df["ma"], 
            mode="lines", 
            name=f"추세 ({ma_window}개{freq_label} 이동평균)", 
            line=dict(color="royalblue", width=3)
            ))
        
        fig.update_layout(
            yaxis=dict(range=[1, 5]),
            xaxis_title="날짜",
            yaxis_title="평균 평점",
            hovermode="x unified",
            template="plotly_white",
            height=350
        )

        st.plotly_chart(fig, use_container_width=True)

# ===== 추천 페이지 =====
if not is_initial:
    if selected_product:
        st.subheader("이 상품과 유사한 추천 상품")
    else:
        st.subheader("검색 결과")

if is_initial:
    st.info("왼쪽 사이드바 또는 검색어를 입력하여 상품을 찾아보세요.")
else:
    # 제품 필터링
    filtered_df = product_filter(df, search_text, selected_sub_cat, selected_skin, min_rating, max_rating, min_price, max_price)

    # 추천 목록에서 선택 상품 제외
    if selected_product:
        filtered_df = filtered_df[filtered_df["product_name"] != selected_product]

    badge_order = {"BEST": 0, "추천": 1, "": 2}
    filtered_df["badge_rank"] = filtered_df["badge"].map(badge_order).fillna(2)

    filtered_df = filtered_df.sort_values(by=["badge_rank", "score", "total_reviews"], ascending=[True, False, False])

    # 페이지네이션
    items_page = 6
    total_items = len(filtered_df)
    total_pages = max(1, math.ceil(total_items / items_page))

    # 페이지 초기화
    if "page" not in st.session_state:
        st.session_state.page = 1

    st.session_state.page = min(st.session_state.page, total_pages)

    cur_filter = (search_text, tuple(selected_sub_cat), tuple(selected_skin), min_rating, max_rating, min_price, max_price)

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
            col_btn, col_card, col_space = st.columns([1.2, 6.5, 2.3])  # 레이아웃
            # 카드 컨테이너 안에서 버튼, 내용 배치
            with col_card:
                with st.container(border=True):

                    # 오른쪽 선택 버튼
                    top_left, top_right = st.columns([8, 2], vertical_alignment="center")
                    with top_right:
                        st.button(
                            "선택",
                            key=f"reco_select_{st.session_state.page}_{i}",
                            on_click=select_product_from_reco,
                            args=(row["product_name"],),
                            use_container_width=True,  # 버튼이 컬럼 폭을 꽉 채움
                        )

                    # 카드형 UI
                    col_image, col_info = st.columns([3, 7])

                    with col_image:
                        # 제품 이미지
                        st.image(row["image_url"], width=200)

                    with col_info:
                        badge_html = ""
                        if row.get("badge") == "BEST":
                            badge_html = "<span style='background:#ffea00;padding:2px 8px;border-radius:8px;font-size:12px;margin-left:8px;'>BEST</span>"
                        if row.get("badge") == "추천":
                            badge_html = "<span style='background:#d1f0ff;padding:2px 8px;border-radius:8px;font-size:12px;margin-left:8px;'>추천</span>"

                        st.markdown(
                            f"""
                            <div style="font-size:14px;color:#888;">
                                {row.get('brand','')}
                                {badge_html}
                            </div>
                            <div style="font-size:18px;font-weight:600;margin:4px 0;">
                                {row['product_name']}
                            </div>
                            <div style="font-size:15px;color:#111;font-weight:500;">
                                ₩{int(row.get('price',0)):,}
                            </div>
                            <div style="margin-top:6px;font-size:13px;color:#555;">
                                카테고리: {row.get('category_path_norm')}<br>
                                피부 타입: {row.get('skin_type','')}<br>
                                평점: {row.get('score','')}<br>
                                리뷰 수: {int(row.get('total_reviews',0)):,}
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                        if row.get("product_url"):
                            st.link_button("상품 페이지", row["product_url"])

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
        st.button("이전", key="prev_page", on_click=go_prev)

    with col_next:
        # on_click 콜백 방식으로 변경
        st.button("다음", key="next_page", on_click=go_next)

    with col_info:
        st.markdown(
            f"<div style='text-align:center; font-weight:bold;'>"
            f"{st.session_state.page} / {total_pages} 페이지"
            f"</div>",
            unsafe_allow_html=True
        )

css.set_css()
