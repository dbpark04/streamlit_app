"""
제품 상세 정보 컴포넌트
"""

import streamlit as st
import pandas as pd


def render_product_info(product_info: pd.Series):
    """
    선택한 제품의 상세 정보 렌더링

    Args:
        product_info: 제품 정보 Series
    """
    st.subheader("🎁 선택한 제품 정보")

    col1, col2, col3 = st.columns(3)
    col1.metric("제품명", product_info.get("product_name", ""))
    col2.metric(
        "브랜드",
        ("-" if pd.isna(product_info.get("brand")) else str(product_info.get("brand"))),
    )
    col3.metric("피부 타입", product_info.get("skin_type", ""))

    col4, col5, col6 = st.columns(3)
    col4.metric("가격", f"₩{int(product_info.get('price', 0) or 0):,}")
    col5.metric("리뷰 수", f"{int(product_info.get('total_reviews', 0) or 0):,}")
    col6.metric("카테고리", product_info.get("sub_category", ""))

    if product_info.get("product_url"):
        st.link_button("상품 페이지", str(product_info["product_url"]))
