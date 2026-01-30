import streamlit as st


def set_css():
    st.markdown(
        """
                <style>
                [data-testid="stMetricValue"]{
                    font-size: 20px
                }
                </style>
                """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
                <style>
                /* 날짜 초기화 버튼 크기조절 */
                div[data-testid="stButton"][id*="reset_date"] button {
                    padding: 0.25rem;
                    min-height: 36px;
                    width: 40px;
                    border-radius: 8px;
                }
                </style>
                """,
        unsafe_allow_html=True,
    )
