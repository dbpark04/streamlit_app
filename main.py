import streamlit as st
import pandas as pd
import math
import random # 임시
import scroll
from sidebar import sidebar, product_filter
import css
from pathlib import Path

st.set_page_config(layout="wide")

# 요청 시 상단 스크롤 이동 적용
scroll.apply_scroll_to_top_if_requested()

# ===== parquet 로딩 =====
PLACEHOLDER_IMAGE = "https://via.placeholder.com/420x420.png?text=No+Image"

@st.cache_data
def load_parquet():
    base_dir = Path(__file__).resolve().parent
    parquet_path = base_dir / "data" / "integrated_products_vector.parquet"
    df = pd.read_parquet(parquet_path)

    # 기본 결측/타입 안정화
    df["brand"] = df["brand"].fillna("")
    df["skin_type"] = df["skin_type"].fillna("")
    df["category_path"] = df["category_path"].fillna("")
    df["category_normal"] = df["category_normal"].fillna("")
    df["price"] = df["price"].fillna(0).astype(int)
    df["total_reviews"] = df["total_reviews"].fillna(0).astype(int)

    # ---- 기존 UI 호환용 컬럼 생성 (최소 변경 핵심) ----
    # 기존 코드에서 df["product"] 기반으로 동작하므로 product_name을 매핑
    df["product"] = df["product_name"]

    # 카테고리: category_path에서 마지막 2단계 정도를 main/sub로 만들어 UI expander 구조 유지
    def _split_cat(path: str):
        parts = [p.strip() for p in path.split(">")]
        parts = [p for p in parts if p]
        if len(parts) >= 2:
            return parts[-2], parts[-1]
        elif len(parts) == 1:
            return parts[0], parts[0]
        else:
            return "", ""

    cats = df["category_path"].apply(_split_cat)
    df["main_category"] = cats.apply(lambda x: x[0])
    df["sub_category"] = cats.apply(lambda x: x[1])

    # 이미지: 일단 placeholder 고정 (나중에 image_url 컬럼 생기면 여기만 바꾸면 됨)
    df["image_url"] = PLACEHOLDER_IMAGE

    # 더미 기반 UI에서 쓰던 컬럼들(표시 비우기)
    df["keyword"] = ""      # 대표 키워드: 비워둠
    df["score"] = 0.0       # 추천 점수: 임시 0.0
    df["badge"] = ""        # BEST/추천 뱃지: 비워둠

    return df


# ===== 데이터프레임 =====
df = load_parquet()

skin_options = df["skin_type"].unique().tolist()
product_options = df["product"].unique().tolist()

# ===== 사이드바 =====
selected_sub_cat, selected_skin, min_rating, max_rating, min_price, max_price = sidebar(df)

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
    col2.metric("브랜드", product_info.get("brand", ""))
    col3.metric("피부 타입", product_info.get("skin_type", ""))

    col4, col5, col6 = st.columns(3)
    col4.metric("가격", f"₩{int(product_info.get('price', 0)):,}")
    col5.metric("리뷰 수", f"{int(product_info.get('total_reviews', 0)):,}")
    col6.metric("카테고리", product_info.get("sub_category", ""))

    if product_info.get("product_url"):
        st.link_button("상품 페이지", product_info["product_url"])


# ===== 추천 페이지 =====
st.subheader("추천 상품")

if is_initial:
    st.info("왼쪽 사이드바 또는 검색어를 입력하여 상품을 찾아보세요.")
else:
    # 제품 필터링
    filtered_df = product_filter(df, search_text, selected_sub_cat, selected_skin, min_rating, max_rating, min_price, max_price)

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
                            args=(row["product"],),
                            use_container_width=True,  # 버튼이 컬럼 폭을 꽉 채움
                        )

                    # 카드형 UI
                    col_image, col_info = st.columns([3, 7])

                    with col_image:
                        # placeholder 이미지
                        st.image(row["image_url"], width="stretch")

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
                                {row['product']}
                            </div>
                            <div style="font-size:15px;color:#111;font-weight:500;">
                                ₩{int(row.get('price',0)):,}
                            </div>
                            <div style="margin-top:6px;font-size:13px;color:#555;">
                                카테고리: {row.get('main_category','')} &gt; {row.get('sub_category','')}<br>
                                피부 타입: {row.get('skin_type','')}<br>
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