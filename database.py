import streamlit as st
from supabase import create_client


def get_connection():
    supabase_url = st.secrets["SUPABASE_URL"].strip().rstrip("/")
    supabase_key = st.secrets["SUPABASE_KEY"].strip()

    supabase = create_client(
        supabase_url,
        supabase_key
    )

    return supabase
