import streamlit as st
st.set_page_config(page_title="Settings", layout="wide")

from session import initialize_session_state
initialize_session_state()


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