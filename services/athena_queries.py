# athena_queries.py
import pandas as pd
import json
from typing import Optional, List
from services.athena_client import (
    athena_read,
    athena_read_cached,
    quote_list,
    quote_str,
)

# 필요하면 여기 테이블명만 바꿔서 전체 반영되게 해두는 게 편함
PRODUCT_TABLE = "coupang_db.integrated_products_final_v3"  # 또는 v3로 변경 가능
REVIEWS_TABLE = "coupang_db.partitioned_reviews_v3"  # 또는 reviews_v3로 변경 가능


SQL_ALL_PRODUCTS = f"""
SELECT
    product_id,
    product_name,
    brand,
    category,
    category_path,
    path,
    price,
    delivery_type,
    product_url,
    skin_type,
    top_keywords,
    avg_rating_with_text,
    avg_rating_without_text,
    text_review_ratio,
    total_reviews,
    rating_1,
    rating_2,
    rating_3,
    rating_4,
    rating_5,
    product_vector_roberta_sentiment,
    representative_review_id_roberta_sentiment,
    representative_similarity_roberta_sentiment,
    product_vector_roberta_semantic,
    representative_review_id_roberta_semantic,
    representative_similarity_roberta_semantic,
    sentiment_score
FROM {PRODUCT_TABLE}
"""


def fetch_all_products(limit: int = 500):
    """
    전체 상품을 다 읽는 건 비용/시간이 커질 수 있어서 기본 limit 권장.
    """
    sql = SQL_ALL_PRODUCTS + f"\nLIMIT {int(limit)}"
    return athena_read_cached(sql)


def fetch_reviews_by_product(product_id: str, category: str = None, limit: int = 300):
    """
    ★중요: reviews_v3는 category 파티션 가능.
    category 조건을 같이 걸면 파티션 프루닝이 타서 빨라지고 비용이 줄어듦.
    """
    pid = quote_str(product_id)

    # category가 제공된 경우 파티션 조건 추가
    where_clause = f"product_id = '{pid}'"
    if category:
        cat = quote_str(category)
        where_clause = f"category = '{cat}' AND {where_clause}"

    sql = f"""
    SELECT
        product_id,
        id,
        full_text,
        title,
        content,
        score,
        date
    FROM {REVIEWS_TABLE}
    WHERE {where_clause}
    ORDER BY date DESC
    LIMIT {int(limit)}
    """
    return athena_read_cached(sql)


def search_products_flexible(
    categories,
    skin_types,
    min_rating,
    max_rating,
    min_price,
    max_price,
    limit: int = 300,
):
    """
    categories/skin_types가 비어있으면 해당 조건은 WHERE에서 제거(=전체 허용)
    + 기본 limit을 걸어 Streamlit/비용 폭주 방지
    """
    where_parts = ["1=1"]

    if categories:
        categories_in = quote_list(categories)
        where_parts.append(f"category IN ({categories_in})")

    if skin_types:
        skin_types_in = quote_list(skin_types)
        where_parts.append(
            f"""
            (
              CASE
                WHEN skin_type LIKE '복합/혼합%' THEN '복합/혼합'
                ELSE skin_type
              END
            ) IN ({skin_types_in})
            """.strip()
        )

    where_parts.append(
        f"avg_rating_with_text BETWEEN {float(min_rating)} AND {float(max_rating)}"
    )
    where_parts.append(f"price BETWEEN {int(min_price)} AND {int(max_price)}")

    where_sql = "\n  AND ".join(where_parts)

    sql = f"""
    SELECT
      product_id,
      product_name,
      brand,
      category,
      price,
      skin_type,
      total_reviews,
      avg_rating_with_text,
      rating_1,
      rating_2,
      rating_3,
      rating_4,
      rating_5,
      sentiment_score,
      top_keywords,
      product_url
    FROM {PRODUCT_TABLE}
    WHERE {where_sql}
    ORDER BY total_reviews DESC, avg_rating_with_text DESC
    LIMIT {int(limit)}
    """
    return athena_read_cached(sql)


def load_products_data_from_athena(
    categories: Optional[List[str]] = None,
    vector_type: str = "roberta_semantic",
    table_name: str = "coupang_db.integrated_products_final_v2",
):
    vector_col = f"product_vector_{vector_type}"

    where_clause = ""
    if categories:
        cat_list = quote_list(categories)
        where_clause = f"WHERE category IN ({cat_list})"

    sql = f"""
    SELECT
        product_id,
        product_name,
        brand,
        category,
        sentiment_score,
        avg_rating_with_text,
        total_reviews,
        product_url,
        price,
        top_keywords,
        product_vector_roberta_semantic
    FROM {table_name}
    {where_clause}
    """

    df = athena_read_cached(sql)

    if (
        not df.empty
        and df[vector_col].dtype == object
        and isinstance(df[vector_col].iloc[0], str)
    ):
        df[vector_col] = df[vector_col].apply(json.loads)

    return df


def fetch_representative_review_text(product_id: str, review_id: int):
    """딱 1개의 리뷰 텍스트만 쿼리하여 속도 극대화"""
    pid = quote_str(product_id)
    # SQL WHERE절에 review_id를 직접 넣는 것이 핵심입니다.
    sql = f"""
    SELECT full_text, title, content
    FROM {REVIEWS_TABLE}
    WHERE product_id = '{pid}' AND id = {int(review_id)}
    LIMIT 1
    """
    return athena_read_cached(sql)
