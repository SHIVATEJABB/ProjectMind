import streamlit as st
st.set_page_config(page_title="ProjectMind", page_icon="assets/favicon.png", layout="wide", initial_sidebar_state="expanded")

from session import initialize_session_state
initialize_session_state()

st.markdown(
    f"<div style='color: gray; font-size: 0.9em; margin-bottom: 10px;'>"
    f"Settings"
    f"</div>",
    unsafe_allow_html=True
)


def settings_page():
    st.title("Settings")

    st.checkbox("Ignore Greetings", value=True)

    st.checkbox("Ignore Meeting Scheduling", value=True)

    st.checkbox("Require Evidence", value=True)

    st.selectbox(
        "Default Report Period",
        ["Last 7 Days", "Last 14 Days", "Last 30 Days", "Custom"],
    )


settings_page()