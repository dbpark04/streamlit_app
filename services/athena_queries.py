# athena_queries.py
import pandas as pd
import json
from typing import Optional, List
from services.athena_client import athena_read, quote_list

SQL_ALL_PRODUCTS = """
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
FROM coupang_db.integrated_products_final_v3
"""


def fetch_all_products():
    return athena_read(SQL_ALL_PRODUCTS)


def fetch_reviews_by_product(product_id: str):
    pid = str(product_id).replace("'", "''")
    sql = f"""
    SELECT
        product_id,
        id,
        full_text,
        title,
        content,
        score,
        date
    FROM coupang_db.reviews_v3
    WHERE product_id = '{pid}'
    ORDER BY date DESC
    """
    return athena_read(sql)


def search_products_flexible(
    categories, skin_types, min_rating, max_rating, min_price, max_price, limit=None
):
    """
    categories/skin_types가 비어있으면 해당 조건은 WHERE에서 제거(=전체 허용)
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

    limit_sql = f"\nLIMIT {int(limit)}" if limit else ""

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
    FROM coupang_db.integrated_products_final_v3
    WHERE {where_sql}
    ORDER BY total_reviews DESC, avg_rating_with_text DESC
    {limit_sql}
    """
    return athena_read(sql)


def load_products_data_from_athena(
    categories: Optional[List[str]] = None,
    vector_type: str = "roberta_semantic",
    table_name: str = "coupang_db.integrated_products_final_v3",
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

    df = athena_read(sql)

    if (
        not df.empty
        and df[vector_col].dtype == object
        and isinstance(df[vector_col].iloc[0], str)
    ):
        df[vector_col] = df[vector_col].apply(json.loads)

    return df


# athena_queries.py
def fetch_representative_review_text(product_id: str, review_id: int):
    """딱 1개의 리뷰 텍스트만 쿼리하여 속도 극대화"""
    pid = str(product_id).replace("'", "''")
    # SQL WHERE절에 review_id를 직접 넣는 것이 핵심입니다.
    sql = f"""
    SELECT full_text, title, content
    FROM coupang_db.reviews_v3
    WHERE product_id = '{pid}' AND id = {int(review_id)}
    LIMIT 1
    """
    return athena_read(sql)
