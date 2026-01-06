import streamlit as st

def set_css():
    st.markdown("""
                <style>
                [data-testid="stMetricValue"]{
                    font-size: 20px
                }
                </style>
                """, unsafe_allow_html=True)
    