# athena_client.py
import streamlit as st
import awswrangler as wr
import boto3
from typing import Iterable, Optional


@st.cache_resource
def get_boto3_session():
    # AWS 환경(EC2/ECS 등)에서는 IAM Role 권장
    return boto3.Session(
        region_name=st.secrets["AWS_REGION"],
        aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"],
    )


def athena_read(sql: str):
    """
    원본 Athena 조회 (캐시 없음).
    """
    session = get_boto3_session()
    return wr.athena.read_sql_query(
        sql=sql,
        database=st.secrets["ATHENA_DB"],
        s3_output=st.secrets["ATHENA_S3_OUTPUT"],
        workgroup=st.secrets.get("ATHENA_WORKGROUP", None),
        boto3_session=session,
        ctas_approach=False,
    )


@st.cache_data(ttl=300, show_spinner=False)
def athena_read_cached(sql: str):
    """
    같은 SQL 반복 호출 시 Athena 비용/시간을 줄이기 위한 캐시 버전.
    - ttl=300: 5분 캐시
    """
    return athena_read(sql)


def quote_list(values: Optional[Iterable]):
    """
    Athena IN (...)에 문자열 리스트를 안전하게 넣기
    ["A","B"] -> 'A','B'
    """
    if not values:
        return ""
    safe = []
    for v in values:
        v = str(v).replace("'", "''")
        safe.append(f"'{v}'")
    return ",".join(safe)


def quote_str(value: str) -> str:
    """
    단일 문자열 리터럴 안전 처리.
    """
    return str(value).replace("'", "''")
