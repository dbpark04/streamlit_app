import pandas as pd
from pathlib import Path
import pyarrow.dataset as ds
import streamlit as st
import re
import ast

@st.cache_data
def load_raw_df(parquet_root: Path) -> pd.DataFrame:
    dataset = ds.dataset(parquet_root, format="parquet", partitioning="hive")
    table = dataset.to_table()
    df = table.to_pandas()

    if "category" in df.columns:
        df["category"] = df["category"].str.replace("_", "/", regex=False)
        
    return df

@st.cache_data
def make_df(df: pd.DataFrame) -> pd.DataFrame:
    rating_df = df.groupby("product_id", as_index=False).agg({
        "rating_1": "sum",
        "rating_2": "sum",
        "rating_3": "sum",
        "rating_4": "sum",
        "rating_5": "sum",
        "total_reviews": "sum",
    })

    # 상품 평점
    rating_df["score"] = (
        rating_df["rating_1"] * 1 + 
        rating_df["rating_2"] * 2 + 
        rating_df["rating_3"] * 3 + 
        rating_df["rating_4"] * 4 + 
        rating_df["rating_5"] * 5
    ) / rating_df["total_reviews"]

    rating_df["score"] = rating_df["score"].round(2)
    rating_df["score"] = rating_df["score"].fillna(0)

    image_url = f"https://tr.rbxcdn.com/180DAY-981c49e917ba903009633ed32b3d0ef7/420/420/Hat/Webp/noFilter"

    # 추천 뱃지
    def calc_badge(score, total_reviews):
        if total_reviews >= 500:
            if score >= 4.8:
                return "BEST"
            elif score >= 4.5:
                return "추천"
        return ""

    rating_df["badge"] = rating_df.apply(lambda x: calc_badge(x["score"], x["total_reviews"]), axis=1)

    # 카테고리 정규화
    main_cats = [
    "스킨케어",
    "클렌징/필링",
    "선케어/태닝",
    "메이크업"
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
        sub = parts[-1] if len(parts) >= 3 else parts[-1] if parts else ""

        return main, middle, sub

    
    df = df.copy()
    df["category_path_norm"] = df["category_path"].apply(norm_cat)
    df[["main_category", "middle_category", "sub_category"]] = df["category_path_norm"].apply(split_category).apply(pd.Series)
    df["image_url"] = image_url
    df["top_keywords"] = df["top_keywords"].apply(lambda x: ", ".join(x))

    product_df = (df[[
                "product_id",
                "product_name",
                "brand",
                "price",
                "image_url",
                "product_url",
                "total_reviews",
                "top_keywords",
                "category",
                "category_path_norm",
                "main_category",
                "middle_category",
                "sub_category",
                "skin_type"
            ]].drop_duplicates("product_id").copy())

    fin_df = product_df.merge(
        rating_df[["product_id", "score", "badge"]],
        on="product_id",
        how="left"
    )

    return fin_df
