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

from load_data import (
    make_df,
    rating_trend,
)  # parquet 로더는 더 이상 안 씀(필요하면 유지 가능)
from sidebar import sidebar  # product_filter는 더 이상 사용 안 함
from recommend_similar_products import recommend_similar_products, print_recommendations
from pathlib import Path

# ✅ Athena 연동
from athena_queries import (
    fetch_all_products,
    fetch_reviews_by_product,
    search_products_flexible,
)


if "product_search" not in st.session_state:
    st.session_state["product_search"] = ""
if "search_keyword" not in st.session_state:
    st.session_state["search_keyword"] = ""
if "page" not in st.session_state:
    st.session_state.page = 1

sys.path.append(os.path.dirname(__file__))

st.set_page_config(layout="wide")

# 그래프 UI 조작 시, 이번 rerun에서는 스크롤 적용 스킵
if "_skip_scroll_apply_once" not in st.session_state:
    st.session_state["_skip_scroll_apply_once"] = False


def _skip_scroll_apply_once():
    st.session_state["_skip_scroll_apply_once"] = True


# 요청 시 상단 스크롤 이동 적용 (단, 그래프 조작 직후 1회는 스킵)
if not st.session_state.get("_skip_scroll_apply_once", False):
    scroll.apply_scroll_to_top_if_requested()
else:
    st.session_state["_skip_scroll_apply_once"] = False


def safe_scroll_to_top():
    scroll.request_scroll_to_top()


# =========================
# ✅ Athena에서 상품 DF 로딩 (전체 메타/추천/옵션용)
# =========================
@st.cache_data(ttl=300)
def load_products_from_athena():
    return fetch_all_products()


product_df = load_products_from_athena()

# make_df가 컬럼 정리용이면 사용, 아니면 fallback
try:
    df = make_df(product_df)
except Exception:
    df = product_df.copy()


# =========================
# ✅ UI가 기대하는 컬럼들 보정/매핑
# =========================
main_cats = [
    "스킨케어",
    "클렌징/필링",
    "선케어/태닝",
    "메이크업",
]


def norm_cat(path):
    if not isinstance(path, str):
        return ""
    parts = [p.strip() for p in path.split(">")]
    for main in main_cats:
        if main in parts:
            idx = parts.index(main)
            return " > ".join(parts[idx:])
    return ""


def split_category(path: str):
    if not isinstance(path, str):
        return "", "", ""
    parts = [p.strip() for p in path.split(">")]
    main = parts[0] if len(parts) >= 1 else ""
    middle = parts[1] if len(parts) >= 2 else ""
    sub = parts[-1] if len(parts) >= 3 else (parts[-1] if parts else "")
    return main, middle, sub


# 카테고리 정규화 보정
if "category_path_norm" not in df.columns:
    if "category_path" in df.columns:
        df["category_path_norm"] = df["category_path"].apply(norm_cat)
    elif "path" in df.columns:
        df["category_path_norm"] = df["path"].apply(norm_cat)
    elif "category" in df.columns:
        df["category_path_norm"] = (
            df["category"].astype(str).str.replace("_", "/", regex=False)
        )
    else:
        df["category_path_norm"] = ""


if "main_category" not in df.columns:
    df[["main_category", "middle_category", "sub_category"]] = (
        df["category_path_norm"].apply(split_category).apply(pd.Series)
    )

if "sub_category" not in df.columns:
    df["sub_category"] = df["category"] if "category" in df.columns else ""

if "score" not in df.columns and "avg_rating_with_text" in df.columns:
    df["score"] = df["avg_rating_with_text"]

if "badge" not in df.columns:
    df["badge"] = ""

image_url = "https://tr.rbxcdn.com/180DAY-981c49e917ba903009633ed32b3d0ef7/420/420/Hat/Webp/noFilter"

if "image_url" not in df.columns:
    df["image_url"] = image_url

if "representative_review_id_roberta" not in df.columns:
    if "representative_review_id_roberta_sentiment" in df.columns:
        df["representative_review_id_roberta"] = df[
            "representative_review_id_roberta_sentiment"
        ]
    elif "representative_review_id_roberta_semantic" in df.columns:
        df["representative_review_id_roberta"] = df[
            "representative_review_id_roberta_semantic"
        ]
    else:
        df["representative_review_id_roberta"] = np.nan

if "product_url" not in df.columns:
    df["product_url"] = ""

if "top_keywords_str" not in df.columns:
    if "top_keywords" in df.columns:
        df["top_keywords_str"] = df["top_keywords"].apply(
            lambda x: (
                ", ".join(map(str, x))
                if isinstance(x, (list, np.ndarray))
                else re.sub(r"[\[\]']", "", str(x))
            )
        )
    else:
        df["top_keywords_str"] = ""

skin_options = (
    df["skin_type"].dropna().unique().tolist() if "skin_type" in df.columns else []
)
product_options = (
    df["product_name"].dropna().unique().tolist()
    if "product_name" in df.columns
    else []
)


# =========================
# ✅ Athena 리뷰 로딩 유틸
# =========================
@st.cache_data(ttl=300)
def load_reviews_athena(product_id: str):
    return fetch_reviews_by_product(product_id)


def get_representative_review_text(reviews_df: pd.DataFrame, review_id):
    if reviews_df is None or reviews_df.empty:
        return ""
    if "id" not in reviews_df.columns:
        return ""

    try:
        rid = int(review_id)
    except Exception:
        return ""

    hit = reviews_df[reviews_df["id"] == rid]
    if hit.empty:
        return ""

    row = hit.iloc[0]
    full_text = row.get("full_text", None)
    if isinstance(full_text, str) and full_text.strip():
        return full_text.strip()

    title = str(row.get("title", "") or "")
    content = str(row.get("content", "") or "")
    return (title + "\n\n" + content).strip()


# =========================
# ✅ Athena 필터 검색 (캐시)
# - st.cache_data는 list가 해시 안 될 수 있어 tuple로 받음
# =========================
@st.cache_data(ttl=300)
def search_products_athena_cached(categories_t, skins_t, min_r, max_r, min_p, max_p):
    categories = list(categories_t) if categories_t else []
    skins = list(skins_t) if skins_t else []
    return search_products_flexible(categories, skins, min_r, max_r, min_p, max_p)


# ===== 사이드바 =====
selected_sub_cat, selected_skin, min_rating, max_rating, min_price, max_price = sidebar(
    df
)

# ===== 메인 =====
st.title("🎀 화장품 추천 대시보드")
st.markdown("---")

search_keyword = st.session_state.get("search_keyword", "")


# 제품 선택 해제 버튼
def clear_selected_product():
    st.session_state["product_search"] = ""
    st.session_state["search_keyword"] = ""
    safe_scroll_to_top()


# selectbox 컨테이너 안으로 이동
with st.container(border=True):
    col_text, col_sel, col_clear = st.columns([5, 5, 1], vertical_alignment="bottom")

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
            on_click=lambda: (
                st.session_state.update({"product_search": "", "search_keyword": ""}),
                safe_scroll_to_top(),
            ),
        )


# 추천 상품 클릭
def select_product_from_reco(product_name: str):
    st.session_state["product_search"] = product_name
    st.session_state["search_keyword"] = product_name
    safe_scroll_to_top()


# 검색어로 사용할 값
if st.session_state.product_search:
    search_text = st.session_state.product_search
else:
    search_text = st.session_state.search_keyword.strip()

# 초기 상태 여부
is_initial = not search_text and not selected_sub_cat and not selected_skin


# ===== 인기상품 TOP 5 =====
if is_initial:
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
    for i, row in enumerate(popular_df.iterrows()):
        row = row[1]
        with cols[i]:
            with st.container(border=True):
                if row.get("image_url"):
                    st.image(
                        row["image_url"], use_container_width=True, output_format="PNG"
                    )

                st.markdown(
                    f"""
                    <div style="font-size:14px;color:#888;margin-top:4px;">
                    {row.get('brand','')}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                st.markdown(
                    f"""
                    <div style="font-size:13px;font-weight:500;line-height:1.3;margin:2px 0;">
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
                        key=f"reco_select_{st.session_state.page}_{i}",
                        on_click=select_product_from_reco,
                        args=(row.get("product_name", ""),),
                        use_container_width=True,
                    )

    st.markdown("---")


# =========================
# ✅ 제품 정보(선택 시)
# =========================
if selected_product:

    # ?
    # def handle_back():
    #     st.session_state["product_search"] = ""
    #     st.session_state["search_keyword"] = ""  # 필요 시 키워드도 같이 초기화
    #     # safe_scroll_to_top() # 필요 시 추가

    # # 버튼에 on_click 인자를 넘겨줍니다.
    # st.button("⬅️ 검색 결과로 돌아가기", on_click=handle_back)

    # st.markdown("---")
    product_rows = df[df["product_name"] == selected_product]
    if product_rows.empty:
        st.warning("선택한 제품 정보를 찾을 수 없어요.")
    else:
        product_info = product_rows.iloc[0]

        st.subheader("🎁 선택한 제품 정보")
        col1, col2, col3 = st.columns(3)

        col1.metric("제품명", product_info.get("product_name", ""))
        col2.metric(
            "브랜드",
            (
                "-"
                if pd.isna(product_info.get("brand"))
                else str(product_info.get("brand"))
            ),
        )

        col3.metric("피부 타입", product_info.get("skin_type", ""))

        col4, col5, col6 = st.columns(3)
        col4.metric("가격", f"₩{int(product_info.get('price', 0) or 0):,}")
        col5.metric("리뷰 수", f"{int(product_info.get('total_reviews', 0) or 0):,}")
        col6.metric("카테고리", product_info.get("sub_category", ""))

        if product_info.get("product_url"):
            st.link_button("상품 페이지", str(product_info["product_url"]))

        st.markdown("### 📃 대표 키워드")
        top_kw = product_info.get("top_keywords_str", "")
        if isinstance(top_kw, (list, np.ndarray)):
            top_kw = ", ".join(map(str, top_kw))
        st.write(top_kw if top_kw else "-")

        product_id = product_info.get("product_id", "")
        review_id = product_info.get("representative_review_id_roberta", None)

        reviews_df = pd.DataFrame()
        if product_id:
            reviews_df = load_reviews_athena(str(product_id))

        st.markdown("### ✒️ 대표 리뷰")
        text = get_representative_review_text(reviews_df, review_id)
        if not text:
            st.info("대표 리뷰가 없습니다.")
        else:
            st.text(text)

        st.markdown("### 📈 평점 추이")
        if (
            reviews_df.empty
            or "date" not in reviews_df.columns
            or "score" not in reviews_df.columns
        ):
            st.info("평점 추이를 그릴 리뷰 데이터가 없습니다.")
        else:
            review_df = reviews_df[["date", "score"]].copy()
            review_df["date"] = pd.to_datetime(review_df["date"], errors="coerce")
            review_df["score"] = pd.to_numeric(review_df["score"], errors="coerce")
            review_df = review_df.dropna(subset=["date", "score"]).sort_values("date")

            if review_df.empty:
                st.info("평점 추이를 그릴 수 있는 날짜/평점 데이터가 없습니다.")
            else:
                min_date = review_df["date"].min().date()
                max_date = review_df["date"].max().date()

                col_left, col_mid, col_right, _ = st.columns([1, 1, 1, 1])
                with col_left:
                    freq_label = st.selectbox(
                        "평균 기준",
                        ["일간", "주간", "월간"],
                        index=1,
                        key="rating_freq_label",
                        on_change=_skip_scroll_apply_once,
                    )

                freq_map = {"일간": ("D", 7), "주간": ("W", 4), "월간": ("M", 3)}
                freq, ma_window = freq_map[freq_label]

                DATE_RANGE_KEY = "rating_date_range"
                default_date_range = (min_date, max_date)

                with col_mid:
                    date_range = st.date_input(
                        "기간 선택",
                        value=default_date_range,
                        min_value=min_date,
                        max_value=max_date,
                        key=DATE_RANGE_KEY,
                        on_change=_skip_scroll_apply_once,
                    )

                def reset_date_range():
                    _skip_scroll_apply_once()
                    st.session_state[DATE_RANGE_KEY] = (min_date, max_date)

                with col_right:
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.button(
                        "↺",
                        key="reset_date",
                        help="날짜 초기화",
                        on_click=reset_date_range,
                    )

                trend_df = pd.DataFrame()
                is_date_range_ready = False

                if isinstance(date_range, tuple) and len(date_range) == 2:
                    is_date_range_ready = True
                    start_date, end_date = date_range
                    start_date = pd.to_datetime(start_date)
                    end_date = pd.to_datetime(end_date)

                    date_df = review_df.loc[
                        (review_df["date"] >= start_date)
                        & (review_df["date"] <= end_date)
                    ]
                    if not date_df.empty:
                        trend_df = rating_trend(date_df, freq=freq, ma_window=ma_window)
                else:
                    st.info("마지막 날짜를 선택해주세요.📆")

                if is_date_range_ready and not trend_df.empty:
                    fig = go.Figure()
                    fig.add_trace(
                        go.Bar(
                            x=trend_df["date"],
                            y=trend_df["avg_score"],
                            name=f"{freq_label} 평균",
                            marker_color="slateblue",
                            opacity=0.4,
                        )
                    )
                    fig.add_trace(
                        go.Scatter(
                            x=trend_df["date"],
                            y=trend_df["ma"],
                            mode="lines",
                            name=f"추세 ({ma_window}개{freq_label} 이동평균)",
                            line=dict(color="royalblue", width=3),
                        )
                    )
                    fig.update_layout(
                        yaxis=dict(range=[1, 5]),
                        xaxis_title="날짜",
                        yaxis_title="평균 평점",
                        hovermode="x unified",
                        template="plotly_white",
                        height=350,
                    )
                    st.plotly_chart(fig, use_container_width=True)
                elif is_date_range_ready and trend_df.empty:
                    st.info("선택한 기간에 대한 평점 데이터가 없습니다.")


# =========================
# ✅ 추천/검색 헤더
# =========================
if not is_initial:
    if selected_product:
        st.subheader("👍 이 상품과 유사한 추천 상품")
    else:
        st.subheader("🌟 검색 결과")

if is_initial:
    st.info("왼쪽 사이드바 또는 검색어를 입력하여 상품을 찾아보세요.")
else:
    # =========================
    # ✅ (핵심) Athena에서 필터 검색 결과 로딩
    # =========================
    filtered_df = search_products_athena_cached(
        tuple(selected_sub_cat),
        tuple(selected_skin),
        float(min_rating),
        float(max_rating),
        int(min_price),
        int(max_price),
    )

    # UI에서 쓰는 컬럼명 맞추기
    if (
        "score" not in filtered_df.columns
        and "avg_rating_with_text" in filtered_df.columns
    ):
        filtered_df["score"] = filtered_df["avg_rating_with_text"]

    if "image_url" not in filtered_df.columns:
        filtered_df["image_url"] = None
    if "badge" not in filtered_df.columns:
        filtered_df["badge"] = ""
    if "category_path_norm" not in filtered_df.columns:
        filtered_df["category_path_norm"] = (
            filtered_df["category"] if "category" in filtered_df.columns else ""
        )

    # =========================
    # ✅ 키워드/제품명 검색은 Athena 결과에 대해 프론트에서 추가 필터
    # =========================
    if search_text:
        s = search_text.strip()
        # top_keywords는 array/string 섞여 있을 수 있어서 str 변환 후 contains
        filtered_df = filtered_df[
            filtered_df["product_name"]
            .astype(str)
            .str.contains(s, case=False, na=False)
            | filtered_df["brand"].astype(str).str.contains(s, case=False, na=False)
            | filtered_df.get("top_keywords", pd.Series([""] * len(filtered_df)))
            .astype(str)
            .str.contains(s, case=False, na=False)
        ]

    page_df = pd.DataFrame()
    reco_df_view = pd.DataFrame()
    search_df_view = filtered_df.copy()

    # 유사도 / 추천점수 기본값
    search_df_view["reco_score"] = 0.0
    search_df_view["similarity"] = 0.0

    badge_order = {"BEST": 0, "추천": 1, "": 2}
    search_df_view["badge_rank"] = (
        search_df_view.get("badge", "").map(badge_order).fillna(2)
    )

    # =========================
    # ✅ 추천(벡터 기반)은 기존 df(전체 메타) 기준으로 유지
    # =========================
    if selected_product:
        target_product = df[df["product_name"] == selected_product]
        if not target_product.empty:
            target_product_id = target_product.iloc[0]["product_id"]

            reco_results = recommend_similar_products(
                product_id=target_product_id,
                categories=None,
                top_n=100,
            )

            # list일 경우
            if isinstance(reco_results, list):
                reco_list = reco_results
            else:
                # dict일 경우
                reco_list = []
                for _, items in reco_results.items():
                    reco_list.extend(items)

            if reco_list:
                tmp_reco_df = pd.DataFrame(reco_list).rename(
                    columns={
                        "recommend_score": "reco_score",
                        "cosine_similarity": "similarity",
                    }
                )

                merged_df = df.merge(
                    tmp_reco_df[["product_id", "reco_score", "similarity"]],
                    on="product_id",
                    how="left",
                )
                merged_df["reco_score"] = merged_df["reco_score"].fillna(0)
                merged_df["similarity"] = merged_df["similarity"].fillna(0)

                merged_df = merged_df[merged_df["product_id"] != target_product_id]
                reco_df_view = (
                    merged_df.query("reco_score > 0")
                    .sort_values(
                        by=["reco_score", "similarity"], ascending=[False, False]
                    )
                    .head(6)
                )

    # =========================
    # ✅ 페이지네이션 (Athena 결과 기준)
    # =========================
    items_page = 6
    total_items = len(search_df_view)
    total_pages = max(1, math.ceil(total_items / items_page))

    if "page" not in st.session_state:
        st.session_state.page = 1
    st.session_state.page = min(st.session_state.page, total_pages)

    cur_filter = (
        search_text,
        tuple(selected_sub_cat),
        tuple(selected_skin),
        min_rating,
        max_rating,
        min_price,
        max_price,
    )
    if st.session_state.get("prev_filter") != cur_filter:
        st.session_state.page = 1
        st.session_state.prev_filter = cur_filter
        safe_scroll_to_top()

    # 데이터 슬라이싱
    start = (st.session_state.page - 1) * items_page
    end = start + items_page
    if not selected_product:
        page_df = search_df_view.iloc[start:end]
    else:
        page_df = pd.DataFrame()


# =========================
# ✅ 상품 출력
# =========================
if (not is_initial) and (not selected_product) and page_df.empty:
    st.warning("표시할 상품이 없어요.🥺")
elif (not is_initial) and (not selected_product) and (not page_df.empty):
    rows = page_df.reset_index(drop=True)

    for i in range(0, len(rows), 2):
        cols = st.columns(2)
        for j in range(2):
            if i + j < len(rows):
                row = rows.iloc[i + j]
                with cols[j]:
                    with st.container(border=True):
                        col_image, col_info = st.columns([3, 7])
                        with col_image:
                            st.image(image_url, width=200)
                            # if row.get("image_url"):
                            #     st.image(row["image_url"], width=200)
                            # else:
                            #     st.empty()

                        with col_info:
                            badge_html = ""
                            if row.get("badge") == "BEST":
                                badge_html = "<span style='background:#ffea00;padding:2px 8px;border-radius:8px;font-size:12px;margin-left:8px;'>BEST</span>"
                            elif row.get("badge") == "추천":
                                badge_html = "<span style='background:#d1f0ff;padding:2px 8px;border-radius:8px;font-size:12px;margin-left:8px;'>추천</span>"

                            st.markdown(
                                f"""
                                <div style="font-size:14px;color:#888;">
                                {row.get('brand','')}
                                {badge_html}
                                </div>

                                <div style="font-size:18px;font-weight:600;margin:4px 0;">
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
                                    key=f"reco_select_{st.session_state.page}_{i+j}",
                                    on_click=select_product_from_reco,
                                    args=(row.get("product_name", ""),),
                                    use_container_width=True,
                                )


# ===== 추천 상품 출력 =====
if selected_product:
    if reco_df_view.empty:
        st.info("추천 가능한 유사 상품이 없어요.😥")
    else:
        rows = reco_df_view.reset_index(drop=True)
        for i in range(0, len(rows), 3):
            cols = st.columns(3)
            for j in range(3):
                if i + j < len(rows):
                    row = rows.iloc[i + j]
                    with cols[j]:
                        with st.container(border=True):
                            col_image, col_info = st.columns([3, 7])
                            with col_image:
                                if row.get("image_url"):
                                    st.image(row["image_url"], width=180)
                            with col_info:
                                st.markdown(
                                    f"""
                                    <div style="font-size:14px;color:#888;">
                                    {row.get('brand','')}
                                    </div>

                                    <div style="font-size:18px;font-weight:600;">
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
                                    on_click=select_product_from_reco,
                                    args=(row.get("product_name", ""),),
                                    use_container_width=True,
                                )


# ===== 페이지 이동 =====
show_pagination = selected_product or selected_sub_cat

if show_pagination and "total_pages" in locals() and total_pages > 1:
    st.markdown("---")
    col_prev, col_info, col_next = st.columns([1, 2, 1])

    def go_prev():
        if st.session_state.page > 1:
            st.session_state.page -= 1
            safe_scroll_to_top()

    def go_next():
        if st.session_state.page < total_pages:
            st.session_state.page += 1
            safe_scroll_to_top()

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

css.set_css()
