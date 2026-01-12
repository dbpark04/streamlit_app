import pandas as pd
from pathlib import Path
import streamlit as st
import re
import ast

@st.cache_data(show_spinner=False)
def load_reviews_map(path="data/reviews_map.parquet"):
    p = Path(path)
    if not p.exists():
        return None

    rdf = pd.read_parquet(p)
    if not {"review_id", "review_text"}.issubset(rdf.columns):
        return None

    return rdf

def load_raw_df(parquet_root: Path) -> pd.DataFrame:
    dfs = []

    # 하위 디렉토리까지 모두 검색
    for p in parquet_root.rglob("*.parquet"):
        df = pd.read_parquet(p)

        # category=XXX 폴더명 추출
        category_folder = [part for part in p.parts if "category=" in part]
        category = category_folder[0].replace("category=", "") if category_folder else "기타"
        df["category"] = category

        dfs.append(df)

    if not dfs:
        raise ValueError("parquet 파일을 찾지 못했습니다.")

    return pd.concat(dfs, ignore_index=True)

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
                "category_path_norm",
                "main_category",
                "middle_category",
                "sub_category",
                "skin_type"
            ]].drop_duplicates("product_id").copy())


    # 대표 리뷰 3개
    if "representative_review_id" in df.columns:
        rep_series = (
            df.groupby("product_id")["representative_review_id"].apply(lambda x: [v for v in x if pd.notna(v)]))
        product_df["representative_review_id"] = product_df["product_id"].map(lambda p: rep_series.get(p, [])[:3])
    else:
        product_df["representative_review_id"] = [[] for _ in range(len(product_df))]

    fin_df = product_df.merge(
        rating_df[["product_id", "score", "badge"]],
        on="product_id",
        how="left"
    )

    return fin_df

@st.cache_data(show_spinner=False)
def load_reviews_df(reviews_path):
    """
    reviews 파일 로드 (parquet/csv)
    최소 컬럼: review_id, review_text (또는 content/text)
    """
    from pathlib import Path
    reviews_path = Path(reviews_path)
    if not reviews_path.exists():
        raise FileNotFoundError(f"리뷰 파일을 찾지 못했습니다: {reviews_path}")

    if reviews_path.suffix.lower() == ".parquet":
        rdf = pd.read_parquet(reviews_path)
    elif reviews_path.suffix.lower() == ".csv":
        rdf = pd.read_csv(reviews_path)
    else:
        raise ValueError("지원하지 않는 리뷰 파일 형식입니다. parquet 를 사용하세요.")

    # 컬럼명 표준화
    if "review_text" not in rdf.columns:
        for cand in ["content", "text", "review", "review_content"]:
            if cand in rdf.columns:
                rdf = rdf.rename(columns={cand: "review_text"})
                break

    if "review_id" not in rdf.columns or "review_text" not in rdf.columns:
        raise ValueError("리뷰 파일에 review_id, review_text 컬럼이 필요합니다.")

    rdf = rdf[["review_id", "review_text"]].copy()
    return rdf

def get_representative_texts(representative_review_id, reviews_df, n=3):
    """
    representative_review_id(단일/리스트/문자열)을 받아
    reviews_df에서 review_text n개를 찾아 리스트로 반환
    """
    if reviews_df is None or reviews_df.empty:
        return []

    rid = representative_review_id
    if rid is None or (isinstance(rid, float) and pd.isna(rid)):
        return []

    if isinstance(rid, str):
        try:
            rid = ast.literal_eval(rid)
        except Exception:
            rid = [x.strip() for x in re.split(r"[;,]", rid) if x.strip()]

    if isinstance(rid, (list, tuple, set)):
        rid_list = list(rid)

    else:
        rid_list = [rid]

    rid_list = rid_list[:n]

    review_map = dict(zip(reviews_df["review_id"].astype(str), reviews_df["review_text"]))
    return [review_map[str(x)] for x in rid_list if str(x) in review_map and isinstance(review_map[str(x)], str)]
