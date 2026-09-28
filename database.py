import streamlit as st
from supabase import create_client


def get_connection():
    url = st.secrets["SUPABASE_URL"].strip().rstrip("/")
    key = st.secrets["SUPABASE_KEY"].strip()

    st.write("Supabase URL loaded:", url[:30] + "...")

    supabase = create_client(url, key)

    return supabase
