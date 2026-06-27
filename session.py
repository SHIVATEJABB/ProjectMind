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
