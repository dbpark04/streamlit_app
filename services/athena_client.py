# athena_client.py
import streamlit as st
import awswrangler as wr
import boto3


@st.cache_resource
def get_boto3_session():
    # AWS 환경(EC2/ECS 등)에서는 IAM Role 권장
    return boto3.Session(
        region_name=st.secrets["AWS_REGION"],
        aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"],
    )


def athena_read(sql: str):
    session = get_boto3_session()
    return wr.athena.read_sql_query(
        sql=sql,
        database=st.secrets["ATHENA_DB"],
        s3_output=st.secrets["ATHENA_S3_OUTPUT"],
        workgroup=st.secrets.get("ATHENA_WORKGROUP", None),
        boto3_session=session,
        ctas_approach=False,
    )


def quote_list(values):
    """
    Athena IN (...)에 문자열 리스트를 안전하게 넣기
    ["A","B"] -> 'A','B'
    """
    safe = []
    for v in values:
        v = str(v).replace("'", "''")
        safe.append(f"'{v}'")
    return ",".join(safe)
