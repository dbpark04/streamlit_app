"""
데이터 로딩 및 컬럼 정규화 유틸리티
"""

import streamlit as st
import pandas as pd
import numpy as np
import re

from utils.load_data import make_df
from services.athena_queries import fetch_all_products, fetch_reviews_by_product

# 메인 카테고리 목록
MAIN_CATS = [
    "스킨케어",
    "클렌징/필링",
    "선케어/태닝",
    "메이크업",
]

DEFAULT_IMAGE_URL = "https://tr.rbxcdn.com/180DAY-981c49e917ba903009633ed32b3d0ef7/420/420/Hat/Webp/noFilter"


def norm_cat(path: str) -> str:
    """카테고리 경로 정규화"""
    if not isinstance(path, str):
        return ""
    parts = [p.strip() for p in path.split(">")]
    for main in MAIN_CATS:
        if main in parts:
            idx = parts.index(main)
            return " > ".join(parts[idx:])
    return ""


def split_category(path: str) -> tuple:
    """카테고리 경로를 main/middle/sub로 분리"""
    if not isinstance(path, str):
        return "", "", ""
    parts = [p.strip() for p in path.split(">")]
    main = parts[0] if len(parts) >= 1 else ""
    middle = parts[1] if len(parts) >= 2 else ""
    sub = parts[-1] if len(parts) >= 3 else (parts[-1] if parts else "")
    return main, middle, sub


@st.cache_data(ttl=300, show_spinner=False)
def load_products_from_athena() -> pd.DataFrame:
    """Athena에서 전체 상품 데이터 로드"""
    return fetch_all_products()


@st.cache_data(ttl=300, show_spinner=False)
def load_reviews_athena(product_id: str) -> pd.DataFrame:
    """Athena에서 리뷰 데이터 로드"""
    return fetch_reviews_by_product(product_id)


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """UI에서 사용할 컬럼들 정규화 및 매핑"""
    df = df.copy()

    # 카테고리 정규화
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

    # main/middle/sub 카테고리 분리
    if "main_category" not in df.columns:
        df[["main_category", "middle_category", "sub_category"]] = (
            df["category_path_norm"].apply(split_category).apply(pd.Series)
        )

    if "sub_category" not in df.columns:
        df["sub_category"] = df["category"] if "category" in df.columns else ""

    # 평점 컬럼
    if "score" not in df.columns and "avg_rating_with_text" in df.columns:
        df["score"] = df["avg_rating_with_text"]

    # 뱃지 초기화
    if "badge" not in df.columns:
        df["badge"] = ""
    df["badge"] = df["badge"].fillna("").astype(str)

    # 뱃지 계산
    if "total_reviews" in df.columns:
        tr = pd.to_numeric(df["total_reviews"], errors="coerce").fillna(0)
        need = df["badge"].eq("")
        best = need & (tr >= 200) & (df["score"] >= 4.9)
        reco = need & (tr >= 200) & (df["score"] >= 4.8) & (~best)
        df.loc[best, "badge"] = "BEST"
        df.loc[reco, "badge"] = "추천"

    # 이미지 URL
    if "image_url" not in df.columns:
        df["image_url"] = DEFAULT_IMAGE_URL

    # 대표 리뷰 ID
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

    # 제품 URL
    if "product_url" not in df.columns:
        df["product_url"] = ""

    # 키워드 문자열
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

    return df


def prepare_dataframe() -> pd.DataFrame:
    """메인 DataFrame 준비"""
    product_df = load_products_from_athena()

    try:
        df = make_df(product_df)
    except Exception:
        df = product_df.copy()

    df = normalize_columns(df)
    return df


def get_options(df: pd.DataFrame) -> tuple:
    """사이드바/검색용 옵션 목록 반환"""
    skin_options = (
        df["skin_type"].dropna().unique().tolist() if "skin_type" in df.columns else []
    )
    product_options = (
        df["product_name"].dropna().unique().tolist()
        if "product_name" in df.columns
        else []
    )
    return skin_options, product_options


def apply_filters(
    df: pd.DataFrame,
    selected_sub_cat: list,
    selected_skin: list,
    min_rating: float,
    max_rating: float,
    min_price: int,
    max_price: int,
    search_text: str = "",
) -> pd.DataFrame:
    """필터 조건 적용"""
    filtered_df = df.copy()

    # 카테고리 필터
    if selected_sub_cat:
        filtered_df = filtered_df[filtered_df["sub_category"].isin(selected_sub_cat)]

    # 피부 타입 필터
    if selected_skin:
        filtered_df = filtered_df[filtered_df["skin_type"].isin(selected_skin)]

    # 평점 필터
    filtered_df = filtered_df[
        (filtered_df["score"] >= min_rating) & (filtered_df["score"] <= max_rating)
    ]

    # 가격 필터
    filtered_df = filtered_df[
        (filtered_df["price"] >= min_price) & (filtered_df["price"] <= max_price)
    ]

    # 컬럼 보정
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

    # 키워드/제품명 검색
    if search_text:
        s = search_text.strip()
        filtered_df = filtered_df[
            filtered_df["product_name"]
            .astype(str)
            .str.contains(s, case=False, na=False)
            | filtered_df["brand"].astype(str).str.contains(s, case=False, na=False)
            | filtered_df.get("top_keywords", pd.Series([""] * len(filtered_df)))
            .astype(str)
            .str.contains(s, case=False, na=False)
        ]

    return filtered_df


def sort_products(df: pd.DataFrame, sort_option: str) -> pd.DataFrame:
    """정렬 옵션 적용"""
    df = df.copy()

    # 유사도/추천점수 기본값
    if "reco_score" not in df.columns:
        df["reco_score"] = 0.0
    if "similarity" not in df.columns:
        df["similarity"] = 0.0

    # 뱃지 순서
    badge_order = {"BEST": 0, "추천": 1, "": 2}
    df["badge_rank"] = df.get("badge", "").map(badge_order).fillna(2)

    if sort_option == "추천순":
        df = df.sort_values(
            by=["badge_rank", "score", "total_reviews"],
            ascending=[True, False, False],
        )
    elif sort_option == "평점 높은 순":
        df = df.sort_values(
            by=["score", "total_reviews"],
            ascending=[False, False],
        )
    elif sort_option == "리뷰 많은 순":
        df = df.sort_values(
            by=["total_reviews", "score"],
            ascending=[False, False],
        )
    elif sort_option == "가격 낮은 순":
        df = df.sort_values(
            by=["price", "score"],
            ascending=[True, False],
        )
    elif sort_option == "가격 높은 순":
        df = df.sort_values(
            by=["price", "score"],
            ascending=[False, False],
        )
    else:
        # 기본 정렬
        df = df.sort_values(
            by=["badge_rank", "score", "total_reviews"],
            ascending=[True, False, False],
        )

    return df
