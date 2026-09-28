import streamlit as st
from supabase import create_client, Client


@st.cache_resource
def get_connection() -> Client:
    supabase_url = st.secrets["SUPABASE_URL"].strip().rstrip("/")
    supabase_key = st.secrets["SUPABASE_KEY"].strip()

    return create_client(
        supabase_url,
        supabase_key
    )
