import streamlit as st
st.set_page_config(page_title="ProjectMind", page_icon="assets/favicon.png", layout="wide", initial_sidebar_state="expanded")

from session import initialize_session_state
initialize_session_state()


st.switch_page("pages/Dashboard.py")
