"""
유사 추천 상품 로직
"""

import streamlit as st
import pandas as pd

from services.recommend_similar_products import recommend_similar_products


def get_recommendations(
    df: pd.DataFrame,
    selected_product: str,
) -> pd.DataFrame:
    """
    선택한 상품과 유사한 추천 상품 조회

    Args:
        df: 전체 상품 DataFrame
        selected_product: 선택한 상품명

    Returns:
        추천 상품 DataFrame (최대 6개)
    """
    reco_df_view = pd.DataFrame()

    target_product = df[df["product_name"] == selected_product]
    if target_product.empty:
        return reco_df_view

    target_product_id = target_product.iloc[0]["product_id"]

    # 캐시 확인
    if st.session_state.get("reco_target_product_id") != target_product_id:
        reco_results = recommend_similar_products(
            product_id=target_product_id,
            categories=None,
            top_n=100,
        )

        if isinstance(reco_results, list):
            reco_list = reco_results
        else:
            reco_list = []
            for _, items in reco_results.items():
                reco_list.extend(items)

        st.session_state["reco_cache"] = reco_list
        st.session_state["reco_target_product_id"] = target_product_id
    else:
        reco_list = st.session_state.get("reco_cache", [])

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
            .sort_values(by=["reco_score", "similarity"], ascending=[False, False])
            .head(6)
        )

    return reco_df_view
