import streamlit as st

def get_secret(section, key, default=""):
    try:
        return st.secrets.get(section, {}).get(key, default)
    except Exception:
        return default
