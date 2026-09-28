import streamlit as st
from supabase import create_client


def get_connection():
    supabase_url=
st.secrets["SUPABASE_URL"].STRIP().RSTRIP("/")
    supabase_key=
st.secrets["SUPABASE_KEY"].strip()
    supabase = create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )

    return supabase
