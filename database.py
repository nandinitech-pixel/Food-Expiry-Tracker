import streamlit as st
from supabase import create_client
import socket


def get_connection():
    url = st.secrets["SUPABASE_URL"].strip().rstrip("/")
    key = st.secrets["SUPABASE_KEY"].strip()

    # Get hostname from URL
    hostname = url.replace("https://", "").replace("http://", "").split("/")[0]

    st.write("Supabase URL loaded:", url[:30] + "...")
    st.write("Supabase hostname:", hostname)

    # Test DNS
    try:
        ip = socket.gethostbyname(hostname)
        st.write("DNS working. IP:", ip)
    except Exception as e:
        st.error(f"DNS error: {e}")
        raise

    supabase = create_client(url, key)

    return supabase
