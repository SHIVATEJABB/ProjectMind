import os
import streamlit as st

st.write("API exists:", os.getenv("OPENROUTER_API_KEY") is not None)

key = os.getenv("OPENROUTER_API_KEY")
if key:
    st.write("Key prefix:", key[:10])
    st.write("Key length:", len(key))
else:
    st.write("No API key found")
st.set_page_config(
    page_title="ProjectMind",
    page_icon="assets/logo.png",
    layout="wide",
    initial_sidebar_state="expanded"
)
