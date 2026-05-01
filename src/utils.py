import streamlit as st

def get_secret(section, key, default=None):
    try:
        if section in st.secrets and key in st.secrets[section]:
            return st.secrets[section][key]
    except Exception:
        pass
    try:
        flat_key = f"{section.upper()}_{key.upper()}"
        return st.secrets.get(flat_key, default)
    except Exception:
        return default
