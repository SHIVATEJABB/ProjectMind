import streamlit as st
import os
import json

def initialize_session_state():
    """
    Initializes all required session state variables with clean, safe defaults.
    Restores active report if one was persisted in store.
    """
    defaults = {
        "project_name": "",
        "client_name": "",
        "report_data": None,
        "chat_history": [],
        "search_query": "",
        "search_sender_filter": "All Senders",
        "input_q": "",
        "clear_input_on_next_run": False,
        "employee_notes": "",
        "review_confirmed": False,
        "selected_project": None,
        "selected_report": None,
        "selected_report_id": None,
        "active_report_meta": None,
        "messages": [],
        "period_selection": "Last 7 Days",
        "whatsapp_file_name": None,
        "uploaded_supporting_file": None,
        "previous_report_data": None,
        "entry_mode": "Generate New Report",
        "view_report_details": None,
        "custom_start_date": None,
        "custom_end_date": None,
        "raw_response": "",
        "project_intelligence_engine": None,
        "reporting_period": ""
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # If active_report_meta is None, try restoring from active_project.json
    if st.session_state.active_report_meta is None:
        from utils import load_report_from_store, get_active_report_from_store
        project_id, version = get_active_report_from_store()
        if project_id and version:
            report = load_report_from_store(project_id, version)
            if report:
                st.session_state.project_name = report.get("project_name", "")
                st.session_state.client_name = report.get("client_name", "")
                st.session_state.report_data = report.get("report_data")
                st.session_state.previous_report_data = report.get("report_data")
                st.session_state.messages = report.get("messages", [])
                st.session_state.chat_history = report.get("chat_history", [])
                st.session_state.project_intelligence_engine = report.get("project_intelligence_engine")
                st.session_state.active_report_meta = {
                    "project_id": report["project_id"],
                    "version": report["version"],
                    "generated_date": report["generated_date"],
                    "reporting_period": report.get("reporting_period", "")
                }

    # Custom Sidebar Navigation (native components, no fragile CSS hacks)
    with st.sidebar:
        st.markdown(
            """
            <style>
                [data-testid="stSidebarUserContent"] {
                    padding-top: 1.5rem !important;
                }
                [data-testid="stSidebarNav"] {
                    display: none;
                }
                div[data-testid="stSidebarHeader"] {
                    padding: 0px !important;
                    margin: 0px !important;
                    height: 0px !important;
                    min-height: 0px !important;
                }
                /* Typography Hierarchy: Lighter & Cleaner */
                html, body, [class*="css"] {
                    font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
                }
                h1 {
                    font-weight: 600 !important;
                    font-size: 2rem !important;
                    color: var(--text-color) !important;
                }
                h2 {
                    font-weight: 500 !important;
                    font-size: 1.4rem !important;
                    color: var(--text-color) !important;
                }
                h3 {
                    font-weight: 500 !important;
                    font-size: 1.2rem !important;
                    color: var(--text-color) !important;
                }
                h4, h5, h6 {
                    font-weight: 500 !important;
                    font-size: 1.05rem !important;
                    color: var(--text-color) !important;
                }
                p, span, li, label, div {
                    font-weight: 400 !important;
                }
                strong, b {
                    font-weight: 600 !important;
                }
                
                /* Metrics Card styling */
                .stMetric {
                    background-color: var(--secondary-background-color) !important;
                    padding: 15px !important;
                    border-radius: 8px !important;
                    border: 1px solid rgba(128, 128, 128, 0.1) !important;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.01) !important;
                    height: 90px !important;
                    display: flex !important;
                    flex-direction: column !important;
                    justify-content: center !important;
                }
                
                /* Alignment, Spacing, Padding adjustments */
                div.element-container {
                    margin-bottom: 0.5rem !important;
                }
                [data-testid="column"] {
                    padding: 4px !important;
                }
                [data-testid="stVerticalBlock"] {
                    gap: 0.75rem !important;
                }
                
                /* Hide standard Streamlit header, footer, MainMenu */
                #MainMenu {visibility: hidden;}
                header {visibility: hidden;}
                footer {visibility: hidden;}
                
                /* Buttons and Input consistency (equal height: 38px) */
                .stButton > button, [data-testid="stFormSubmitButton"] > button, .stDownloadButton > button {
                    font-weight: 500 !important;
                    border-radius: 6px !important;
                    padding: 0px 1rem !important;
                    height: 38px !important;
                    line-height: 38px !important;
                    transition: all 0.2s ease-in-out !important;
                    display: inline-flex !important;
                    align-items: center !important;
                    justify-content: center !important;
                }
                
                /* Input element heights */
                div[data-testid="stNumberInput"] input, div[data-testid="stTextInput"] input, .stSelectbox div[role="button"] {
                    height: 38px !important;
                    border-radius: 6px !important;
                }
                
                /* Sidebar links visual styling */
                [data-testid="stSidebar"] a {
                    padding: 0.5rem 0.75rem !important;
                    border-radius: 6px !important;
                    margin-bottom: 6px !important;
                    font-weight: 500 !important;
                    font-size: 0.95rem !important;
                    transition: all 0.2s ease-in-out !important;
                    display: flex !important;
                    align-items: center !important;
                }
                [data-testid="stSidebar"] a:hover {
                    background-color: rgba(128, 128, 128, 0.08) !important;
                    text-decoration: none !important;
                }
            </style>
            """,
            unsafe_allow_html=True
        )
        
        # Display logo at the top (use the logo only, no text below it)
        st.image("assets/logo.png", use_container_width=True)
        st.write("")
        
        # Navigation page links
        st.page_link("pages/Dashboard.py", label="Dashboard")
        st.page_link("pages/Ask_Chitti.py", label="Ask Chitti")
        st.page_link("pages/Reports.py", label="Reports")
        st.page_link("pages/Settings.py", label="Settings")
