import streamlit as st
from session import initialize_session_state

initialize_session_state()
st.switch_page("pages/Dashboard.py")