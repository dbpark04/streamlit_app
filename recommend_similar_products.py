import os
import numpy as np
import pandas as pd
import glob
from typing import List, Optional, Dict, Any
from athena_queries import load_products_data_from_athena


def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    if vec1 is None or vec2 is None:
        return 0.0

    # 벡터가 리스트인 경우 numpy 배열로 변환
    if isinstance(vec1, list):
        vec1 = np.array(vec1)
    if isinstance(vec2, list):
        vec2 = np.array(vec2)

    # 0 벡터인 경우 처리
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return float(np.dot(vec1, vec2) / (norm1 * norm2))


def load_products_data(
    processed_data_dir: str = "./data/processed_data",
    categories: Optional[List[str]] = None,
    vector_type: str = "roberta_semantic",
) -> pd.DataFrame:
    """
    상품 데이터 로드 (integrated_products_final)

    Args:
        processed_data_dir: processed_data 디렉토리 경로
        categories: 로드할 카테고리 리스트 (None이면 전체)
        vector_type: 사용할 벡터 타입 ("roberta", "bert", "koelectra", "word2vec")

    Returns:
        pd.DataFrame: 상품 데이터
    """
    products_final_dir = os.path.join(processed_data_dir, "integrated_products_final")

    # Hive 파티셔닝: category=*/data.parquet 패턴
    if categories is None:
        # 모든 카테고리 로드
        parquet_files = glob.glob(
            os.path.join(products_final_dir, "category=*", "data.parquet")
        )
    else:
        # 특정 카테고리만 로드
        parquet_files = []
        for category in categories:
            file_path = os.path.join(
                products_final_dir, f"category={category}", "data.parquet"
            )
            if os.path.exists(file_path):
                parquet_files.append(file_path)

    if not parquet_files:
        return pd.DataFrame()

    # 모든 파일 로드 및 병합
    dfs = []
    for file_path in parquet_files:
        df = pd.read_parquet(file_path)
        dfs.append(df)

    all_products = pd.concat(dfs, ignore_index=True)

    # 필요한 컬럼 확인
    vector_col = f"product_vector_{vector_type}"
    if vector_col not in all_products.columns:
        raise ValueError(
            f"'{vector_col}' 컬럼이 존재하지 않습니다. "
            f"사용 가능한 벡터 타입을 확인하세요."
        )

    return all_products


def recommend_similar_products(
    product_id: Optional[str] = None,
    categories: Optional[List[str]] = None,
    top_n: int = 10,
    processed_data_dir: str = "./data/processed_data",
    vector_type: str = "roberta_semantic",
    exclude_self: bool = True,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    유사 상품 추천 또는 전체 상품 랭킹

    점수 계산 방식:
    - product_id가 있을 때 (유사 상품 추천):
      점수 = 유사도 * 0.5 + 긍정확률 * 0.3 + 정규화_평점 * 0.2
    - product_id가 None일 때 (전체 랭킹):
      점수 = 긍정확률 * 0.6 + 정규화_평점 * 0.4
    - 정규화_평점 = 평균평점 / 5.0

    Args:
        product_id: 기준 상품 ID (예: "로션_1"), None이면 전체 랭킹
        categories: 검색할 카테고리 리스트 (None이면 모든 카테고리)
        top_n: 반환할 추천 상품 개수 (카테고리별)
        processed_data_dir: processed_data 디렉토리 경로
        vector_type: 사용할 벡터 타입
        exclude_self: 자기 자신을 결과에서 제외할지 여부

    Returns:
        Dict[str, List[Dict]]: 카테고리별 추천 상품 딕셔너리
            {
                "로션": [
                    {
                        "product_id": "로션_2",
                        "product_name": "상품명",
                        "brand": "브랜드",
                        "recommend_score": 0.85,
                        "cosine_similarity": 0.92,
                        "sentiment_score": 0.78,
                        "category": "로션",
                        ...
                    },
                    ...
                ],
                "크림": [...],
                ...
            }
    """
    # 1. 모든 상품 데이터 로드
    print(f"상품 데이터 로드 중... (카테고리: {categories or '전체'})")
    all_products = load_products_data_from_athena(
    categories=categories,
    vector_type=vector_type
)


    if all_products.empty:
        print("[경고] 상품 데이터를 찾을 수 없습니다.")
        return []

    print(f"✓ {len(all_products):,}개 상품 로드 완료")

    # 2. product_id 유무에 따라 분기 처리
    target_vector = None
    target_product_name = None

    if product_id is not None:
        # 유사 상품 추천 모드
        print(f"\n[모드] 유사 상품 추천 (product_id={product_id})")

        # 기준 상품 찾기
        target_product = all_products[all_products["product_id"] == product_id]

        if target_product.empty:
            print(f"[오류] 상품 ID '{product_id}'를 찾을 수 없습니다.")
            return {}

        target_product = target_product.iloc[0]
        target_product_name = target_product.get("product_name", product_id)
        vector_col = f"product_vector_{vector_type}"
        target_vector = target_product[vector_col]

        if target_vector is None or (
            isinstance(target_vector, (list, np.ndarray)) and len(target_vector) == 0
        ):
            print(f"[오류] 상품 '{product_id}'의 벡터가 없습니다.")
            return {}

        print(f"✓ 기준 상품: {target_product_name}")
        print("점수 = 유사도 * 0.5 + 긍정확률 * 0.3 + 정규화_평점 * 0.2")
    else:
        # 전체 랭킹 모드
        print(f"\n[모드] 전체 상품 랭킹")
        print("점수 = 긍정확률 * 0.6 + 정규화_평점 * 0.4")

    # 3. 모든 상품과 비교하여 점수 계산
    print(f"\n점수 계산 중...")
    results = []
    vector_col = f"product_vector_{vector_type}"

    for idx, product in all_products.iterrows():
        # 자기 자신 제외 (옵션)
        if (
            exclude_self
            and product_id is not None
            and product["product_id"] == product_id
        ):
            continue

        # sentiment_score 추출 (없으면 0.5로 기본값)
        sentiment = product.get("sentiment_score")
        if sentiment is None or pd.isna(sentiment):
            sentiment = 0.5

        # 정규화 평점 계산 (평균평점 / 5.0)
        avg_rating = product.get("avg_rating_with_text", 0)
        if avg_rating is None or pd.isna(avg_rating):
            avg_rating = 0
        normalized_rating = avg_rating / 5.0

        if product_id is not None:
            # 유사 상품 추천 모드: 유사도 계산 필요
            product_vector = product[vector_col]

            # 벡터가 없으면 스킵
            if product_vector is None or (
                isinstance(product_vector, (list, np.ndarray))
                and len(product_vector) == 0
            ):
                continue

            # 코사인 유사도 계산
            similarity = cosine_similarity(target_vector, product_vector)

            # 최종 점수 = 유사도 * 0.5 + 긍정확률 * 0.3 + 정규화_평점 * 0.2
            recommend_score = (
                similarity * 0.5 + sentiment * 0.3 + normalized_rating * 0.2
            )
        else:
            # 전체 랭킹 모드: 유사도 불필요
            similarity = None

            # 최종 점수 = 긍정확률 * 0.6 + 정규화_평점 * 0.4
            recommend_score = sentiment * 0.6 + normalized_rating * 0.4

        # 결과 저장
        result = {
            "product_id": product["product_id"],
            "product_name": product.get("product_name", ""),
            "brand": product.get("brand", ""),
            "category": product.get("category", ""),
            "price": product.get("price"),
            "recommend_score": float(recommend_score),
            "sentiment_score": float(sentiment),
            "normalized_rating": float(normalized_rating),
            "avg_rating": float(avg_rating),
            "total_reviews": product.get("total_reviews", 0),
            "avg_rating_with_text": product.get("avg_rating_with_text", 0),
            "top_keywords": product.get("top_keywords", []),
            "product_url": product.get("product_url", ""),
        }

        # 유사도는 product_id가 있을 때만 포함
        if similarity is not None:
            result["cosine_similarity"] = float(similarity)

        results.append(result)

    # 4. 카테고리별로 그룹화
    from collections import defaultdict

    category_results = defaultdict(list)

    for result in results:
        category = result["category"]
        category_results[category].append(result)

    # 5. 각 카테고리별로 점수 높은 순으로 정렬 후 상위 N개 선택
    final_results = {}
    total_count = 0

    for category, products in category_results.items():
        # 점수 높은 순으로 정렬
        products.sort(key=lambda x: x["recommend_score"], reverse=True)
        # 상위 N개 선택
        top_products = products[:top_n]
        final_results[category] = top_products
        total_count += len(top_products)

    print(f"✓ 추천 상품 {total_count}개 생성 완료 ({len(final_results)}개 카테고리)")
    for category, products in final_results.items():
        print(f"  - {category}: {len(products)}개")

    return final_results


def print_recommendations(recommendations: Dict[str, List[Dict[str, Any]]]):
    """
    추천 결과를 보기 좋게 출력

    Args:
        recommendations: recommend_similar_products() 결과 (카테고리별 딕셔너리)
    """
    if not recommendations:
        print("추천 결과가 없습니다.")
        return

    print("\n" + "=" * 100)
    print("추천 상품 목록 (카테고리별)")
    print("=" * 100)

    for category, products in recommendations.items():
        print(f"\n[{category}] - {len(products)}개 상품")
        print("-" * 110)
        print(
            f"{'순위':<5} {'상품명':<30} {'브랜드':<15} {'점수':<8} {'유사도':<8} {'감성':<8} {'평점':<8}"
        )
        print("-" * 110)

        for rank, rec in enumerate(products, 1):
            # None 값 처리
            product_name = rec["product_name"] or ""
            brand = rec["brand"] or ""

            # 길이 제한 적용
            product_name = (
                product_name[:28] + ".." if len(product_name) > 30 else product_name
            )
            brand = brand[:13] + ".." if len(brand) > 15 else brand

            # 유사도는 있을 때만 표시
            similarity_str = (
                f"{rec.get('cosine_similarity', 0.0):<8.3f}"
                if "cosine_similarity" in rec
                else "N/A     "
            )

            print(
                f"{rank:<5} "
                f"{product_name:<30} "
                f"{brand:<15} "
                f"{rec['recommend_score']:<8.3f} "
                f"{similarity_str} "
                f"{rec['sentiment_score']:<8.3f} "
                f"{rec.get('avg_rating', 0):<8.1f}"
            )

    print("\n" + "=" * 100)


# 사용 예시
if __name__ == "__main__":
    # 예시 1: 특정 카테고리에서 추천
    print("=" * 100)
    print("예시 1: 로션 카테고리에서 유사 상품 추천")
    print("=" * 100)

    results = recommend_similar_products(
        product_id="로션_1",
        categories=["로션"],
        top_n=2,
    )

    print_recommendations(results)
    print("\n\n")
    print("=" * 100)

    # 예시 2: 모든 카테고리에서 추천
    print("\n\n" + "=" * 100)
    print("예시 2: 모든 카테고리에서 유사 상품 추천")
    print("=" * 100)

    results = recommend_similar_products(
        product_id="로션_1",
        categories=None,
        top_n=2,
    )

    print_recommendations(results)

    # 예시 3: 상품 미입력 (필터링된것중 전체 랭킹)
    print("\n\n" + "=" * 100)
    print("예시 3: 모든 카테고리에서 유사 상품 추천")
    print("=" * 100)

    results = recommend_similar_products(
        product_id=None,
        categories=None,
        top_n=2,
    )

    print_recommendations(results)

    print("results\n", results)

    print("\n\n" + "=" * 100)

    for category, items in results.items():
        print(f"\nCategory: {category}")
        for item in items:
            print(
                f"  - {item['product_id']}: Score={item['recommend_score']:.3f}, "
                f"Sentiment={item['sentiment_score']:.3f}, "
                f"Avg Rating={item['avg_rating']:.1f}"
            )
