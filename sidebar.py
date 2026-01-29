import streamlit as st
import numpy as np
import re


# 사이드바 함수
def sidebar(df):
    if st.sidebar.button("🏠 홈으로 가기", use_container_width=True):
        # 검색어 및 페이지 초기화
        st.session_state["product_search"] = ""
        st.session_state["search_keyword"] = ""
        st.session_state["page"] = 1

        # 사이드바의 동적 체크박스(카테고리, 피부타입 등) 초기화
        for key in list(st.session_state.keys()):
            if key.startswith(("sub_", "skin_", "all_main_", "all_middle_")):
                st.session_state[key] = False

        # 페이지 상단으로 스크롤 요청 (scroll.py 연동 시)
        st.session_state["_scroll_to_top"] = True

        st.rerun()  # 즉시 반영을 위해 재실행

    st.sidebar.markdown("---")  # 구분선
    st.sidebar.header("검색 조건")
    st.sidebar.subheader("카테고리")

    selected_sub_cat = []

    for main_cat in sorted(df["main_category"].dropna().unique()):
        if not str(main_cat).strip():
            continue

        with st.sidebar.expander(str(main_cat), expanded=False):
            main_df = df[df["main_category"] == main_cat]
            middle_cats = [
                m
                for m in main_df["middle_category"].dropna().unique().tolist()
                if str(m).strip()
            ]

            main_all_key = f"all_main_{main_cat}"
            main_sub_keys = []

            # 중간 카테고리x
            if not middle_cats:
                sub_cats = sorted(main_df["sub_category"].dropna().unique())

                for sub in sub_cats:
                    key = f"sub_{main_cat}_{sub}"
                    main_sub_keys.append(key)

                    if st.checkbox(sub, key=key):
                        selected_sub_cat.append(sub)

            # 중간 카테고리o
            else:
                for middle in sorted(middle_cats):
                    sub_df = main_df[main_df["middle_category"] == middle]
                    sub_cats = sorted(sub_df["sub_category"].dropna().unique())

                    # mid == sub 인 경우: expander 없이 checkbox 하나
                    if len(sub_cats) == 1 and sub_cats[0] == middle:
                        key = f"sub_{main_cat}_{middle}"
                        main_sub_keys.append(key)

                        if st.checkbox(middle, key=key):
                            selected_sub_cat.append(middle)

                    # 일반적인 mid > sub 구조
                    else:
                        with st.expander(middle, expanded=False):
                            middle_all_key = f"all_middle_{main_cat}_{middle}"
                            middle_sub_keys = []

                            def toggle_middle_all(keys, all_key):
                                val = st.session_state.get(all_key, False)
                                for k in keys:
                                    st.session_state[k] = val

                            st.checkbox(
                                "전체 선택",
                                key=middle_all_key,
                                on_change=toggle_middle_all,
                                args=(middle_sub_keys, middle_all_key),
                            )

                            for sub in sub_cats:
                                key = f"sub_{main_cat}_{middle}_{sub}"
                                middle_sub_keys.append(key)
                                main_sub_keys.append(key)

                                if st.checkbox(sub, key=key):
                                    selected_sub_cat.append(sub)

    st.sidebar.caption(f"선택된 카테고리: {len(selected_sub_cat)}개")

    # 피부 타입
    st.sidebar.subheader("피부 타입")

    # 표시 순서
    skin_order = ["건성", "지성", "복합성", "민감성", "여드름성", "미분류", "복합/혼합"]

    available_skins = df["skin_type"].dropna().unique().tolist()
    combined_skin_types = [s for s in available_skins if s.startswith("복합/혼합(")]

    skin_mapping = {"복합/혼합": combined_skin_types}
    ordered_skins = [
        s for s in skin_order if (s in available_skins or s == "복합/혼합")
    ]

    selected_skin = []

    for skin in ordered_skins:
        if st.sidebar.checkbox(skin, key=f"skin_{skin}"):
            if skin in skin_mapping:
                selected_skin.extend(skin_mapping[skin])
            else:
                selected_skin.append(skin)

    # 평점 슬라이더
    st.sidebar.subheader("평점")
    min_rating, max_rating = st.sidebar.slider(
        "평점 범위",
        min_value=0.0,
        max_value=5.0,
        value=(0.0, 5.0),
        step=0.1,
        label_visibility="collapsed",
    )

    # 가격 슬라이더
    st.sidebar.subheader("가격")

    df_min = int(df["price"].min())
    df_max = int(df["price"].max())

    min_price, max_price = st.sidebar.slider(
        "가격 범위",
        min_value=df_min,
        max_value=df_max,
        value=(df_min, df_max),
        step=1000,
        label_visibility="collapsed",
    )

    return selected_sub_cat, selected_skin, min_rating, max_rating, min_price, max_price


# 필터링 함수
def product_filter(
    df,
    search_text,
    selected_sub_cat,
    selected_skin,
    min_rating,
    max_rating,
    min_price,
    max_price,
):
    filtered_df = df.copy()

    # 검색어 조건
    if search_text:
        safe_text = re.escape(search_text)  # 정규식 이스케이프
        filtered_df = filtered_df[
            filtered_df["product_name"].str.contains(safe_text, case=False, na=False)
            | filtered_df["brand"].str.contains(safe_text, case=False, na=False)
            | filtered_df["top_keywords"].str.contains(safe_text, case=False, na=False)
        ]

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

    return filtered_df
