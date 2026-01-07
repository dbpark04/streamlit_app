import streamlit as st

def _toggle_all_subcats(all_key: str, sub_keys: list[str], clicked_flag_key: str):
    """'전체 선택' 체크박스가 변경되었을 때 하위 체크박스들 동기화"""
    val = st.session_state.get(all_key, False)
    for k in sub_keys:
        st.session_state[k] = val
    #  전체선택 클릭 직후, 자동 동기화 로직 일시 차단용 플래그
    st.session_state[clicked_flag_key] = True

# 사이드바 함수
def sidebar(df):
    st.sidebar.header("검색 조건")

    # 카테고리
    st.sidebar.subheader("카테고리")

    selected_sub_cat = []

    for main_cat in df["main_category"].unique():
        with st.sidebar.expander(main_cat, expanded=False):
            sub_cats = (df[df["main_category"] == main_cat]["sub_category"].unique().tolist())
            all_key = f"all_{main_cat}"
            clicked_flag_key = f"{all_key}__clicked"

            # 하위 카테고리 체크박스 key 생성 및 초기 상태 보장
            sub_keys = [f"sub_{main_cat}_{sub}" for sub in sub_cats]
            for k in sub_keys:
                st.session_state.setdefault(k, False)

            # 모든 sub가 선택되었는지 여부 계산 (전체선택 표시용)
            all_selected = all(st.session_state.get(k, False) for k in sub_keys) if sub_keys else False

            # sub 선택 상태를 기준으로 전체선택 체크 상태 자동 동기화 
            if not st.session_state.get(clicked_flag_key, False):
                st.session_state[all_key] = all_selected

            # 전체 선택 체크박스 (클릭했을 때만 sub들을 일괄 변경)
            st.checkbox(
                "전체 선택",
                key=all_key,
                on_change=_toggle_all_subcats,
                args=(all_key, sub_keys, clicked_flag_key),
            )

            # 개별 sub 체크박스 (사용자 선택 상태 그대로 유지)
            for sub, sub_key in zip(sub_cats, sub_keys):
                checked = st.checkbox(sub, key=sub_key)
                if checked:
                    selected_sub_cat.append(sub)

            # 클릭 플래그 리셋 (다음부터 자동 동기화 재개)
            if st.session_state.get(clicked_flag_key, False):
                st.session_state[clicked_flag_key] = False

    st.sidebar.caption(f"선택된 카테고리: {len(selected_sub_cat)}개")

    # 피부 타입
    st.sidebar.subheader("피부 타입")

    selected_skin = []

    for skin in df["skin_type"].unique():
        if st.sidebar.checkbox(skin, key=f"skin_{skin}"):
            selected_skin.append(skin)    

    # 평점 슬라이더
    st.sidebar.subheader("평점")
    min_rating, max_rating = st.sidebar.slider(
        "평점 범위",
        # 최소 평점
        min_value=1.0,
        # 최대 평점
        max_value=5.0,
        # 초기 선택 값
        value=(3.0, 5.0),
        step=0.1
    )

    return selected_sub_cat, selected_skin, min_rating, max_rating

# 필터링 함수
def product_filter(df, search_text, selected_sub_cat, selected_skin, min_rating, max_rating):
    filtered_df = df.copy()

    # 검색어 조건
    if search_text is not None:
        filtered_df = filtered_df[filtered_df["product"].str.contains(search_text, case=False)]

    # 카테고리 필터
    if selected_sub_cat:
        filtered_df = filtered_df[filtered_df["sub_category"].isin(selected_sub_cat)]

    # 피부 타입 필터
    if selected_skin:
        filtered_df = filtered_df[filtered_df["skin_type"].isin(selected_skin)]

    # 평점 필터
    filtered_df = filtered_df[(filtered_df["score"] >= min_rating) & (filtered_df["score"] <= max_rating)]

    # 평점 기준 정렬
    filtered_df = filtered_df.sort_values(by="score", ascending=False)

    return filtered_df