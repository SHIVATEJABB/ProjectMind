import streamlit as st

# Page configuration
st.set_page_config(
    page_title="ProjectMind",
    page_icon="assets/favicon.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Central Session State Initialization
from session import initialize_session_state
initialize_session_state()

import json
import time
import datetime as _datetime_module
from datetime import date, timedelta

from parser import (
    read_text_file,
    extract_messages,
    conversation_summary,
    check_coverage,
    filter_messages_by_date,
    combine_documents,
)
from prompts import build_project_prompt
from ai import analyze_project
from utils import (
    generate_excel_report,
    generate_word_report,
    format_duration,
    get_hours_minutes,
)

# Breadcrumbs (UI Cleanup)
p_meta = st.session_state.get("active_report_meta")
if p_meta is not None:
    proj_name = st.session_state.get('project_name') or 'Unnamed Project'
    version = p_meta.get("version", "1")
    st.markdown(
        f"<div style='color: gray; font-size: 0.9em; margin-bottom: 10px;'>"
        f"Reports &gt; {proj_name} &gt; Report v{version} &gt; Dashboard"
        f"</div>",
        unsafe_allow_html=True
    )
else:
    st.markdown(
        f"<div style='color: gray; font-size: 0.9em; margin-bottom: 10px;'>"
        f"Dashboard"
        f"</div>",
        unsafe_allow_html=True
    )

st.title("ProjectMind")
st.caption("AI-powered project intelligence from workplace conversations.")

# Dashboard Context Card (Part 9 & Active Project Banner)
if st.session_state.get("active_report_meta") is not None:
    meta = st.session_state.active_report_meta
    
    # Calculate conversation coverage status
    coverage_str = "Not Available"
    if st.session_state.get("messages"):
        summary_cov = conversation_summary(st.session_state.messages)
        if summary_cov.get("last"):
            conversation_end = summary_cov["last"].date()
            gap_days = (date.today() - conversation_end).days
            if gap_days <= 0:
                coverage_str = "Up to Date"
            elif gap_days == 1:
                coverage_str = "Missing Today's Messages"
            else:
                coverage_str = f"Outdated by {gap_days} Days"
                
    # Format generated date
    try:
        from datetime import datetime
        gen_d = datetime.strptime(meta["generated_date"], "%Y-%m-%d").strftime("%d %b %Y")
    except Exception:
        gen_d = meta.get("generated_date", "")
        
    with st.container(border=True):
        st.markdown(f"#### Current Project: {st.session_state.project_name}")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.write(f"**Client:** {st.session_state.client_name}")
            st.write(f"**Current Version:** Version {meta.get('version')}")
        with c2:
            st.write(f"**Reporting Period:** {meta.get('reporting_period')}")
            st.write(f"**Last Generated:** {gen_d}")
        with c3:
            st.write(f"**Conversation Coverage:** {coverage_str}")
            if st.button("Back to Reports", key="dashboard_back_to_reports"):
                st.switch_page("pages/Reports.py")
else:
    st.info("No active project selected.")

st.write("")

@st.cache_data
def get_combined_evidence(chat_text, start_date, end_date, supporting_text=""):
    messages = extract_messages(chat_text)
    filtered = filter_messages_by_date(messages, start_date, end_date)
    evidence = combine_documents(filtered, supporting_text)
    return evidence, filtered




# Entry Mode Selector
st.session_state.entry_mode = st.radio(
    "Choose Dashboard Mode",
    ["Generate New Report", "Continue From Existing Report"],
    horizontal=True,
    label_visibility="collapsed"
)

# Display status of current/previous report state if continuing
if st.session_state.previous_report_data:
    p_meta = st.session_state.get("active_report_meta", {})
    v_str = f" v{p_meta.get('version')}" if p_meta.get("version") else ""
    st.info(
        f"Continuing reporting using state from: **{st.session_state.project_name}**{v_str} "
        f"(Client: {st.session_state.client_name})."
    )
    if st.button("Clear Previous State", key="clear_previous_state_btn"):
        st.session_state.previous_report_data = None
        st.session_state.active_report_meta = None
        st.session_state.project_name = ""
        st.session_state.client_name = ""
        st.session_state.report_data = None
        st.session_state.messages = []
        st.session_state.whatsapp_file_name = None
        from utils import clear_active_report_in_store
        clear_active_report_in_store()
        st.rerun()

# Preprocess and synchronize task updates from widget inputs back to st.session_state.report_data
# This runs before any metrics, tasks, or downloads are rendered to keep them synchronized.
if st.session_state.report_data is not None:
    meta = st.session_state.get("active_report_meta")
    updated = False
    if "review_confirmed" in st.session_state:
        val = st.session_state["review_confirmed"]
        if st.session_state.report_data.get("review_confirmed") != val:
            st.session_state.report_data["review_confirmed"] = val
            updated = True
    if "employee_notes" in st.session_state:
        val = st.session_state["employee_notes"]
        if st.session_state.report_data.get("employee_notes") != val:
            st.session_state.report_data["employee_notes"] = val
            updated = True
            
    if updated and meta:
        from utils import update_report_in_store
        update_report_in_store(meta["project_id"], meta["version"], st.session_state.report_data)

# Continue from previous report file upload workflow
if st.session_state.entry_mode == "Continue From Existing Report" and not st.session_state.previous_report_data:
    st.subheader("Upload Previous Report")
    prev_report_file = st.file_uploader(
        "Upload a previous report file (.json, .docx, .xlsx, .txt, .md)",
        type=["json", "docx", "xlsx", "txt", "md"],
        key="prev_report_file_uploader"
    )
    if prev_report_file is not None:
        from utils import extract_text_from_upload, reconstruct_report_from_text
        parsed, is_pm = extract_text_from_upload(prev_report_file)
        if is_pm:
            # Native ProjectMind report
            st.session_state.project_name = parsed.get("project_name", "")
            st.session_state.client_name = parsed.get("client_name", "")
            st.session_state.previous_report_data = parsed.get("report_data")
            st.session_state.report_data = parsed.get("report_data")
            st.session_state.project_intelligence_engine = parsed.get("project_intelligence_engine")
            # Restore messages list if present
            if "messages" in parsed:
                st.session_state.messages = parsed["messages"]
            # Set active report metadata
            st.session_state.active_report_meta = {
                "project_id": parsed["project_id"],
                "version": parsed["version"],
                "generated_date": parsed.get("generated_date", ""),
                "reporting_period": parsed.get("reporting_period", "")
            }
            from utils import set_active_report_in_store
            set_active_report_in_store(parsed["project_id"], parsed["version"])
            # Set date keys if start_date/end_date exist
            if parsed.get("start_date"):
                from datetime import datetime
                try:
                    st.session_state.custom_start_date = datetime.strptime(parsed["start_date"], "%Y-%m-%d").date()
                except Exception:
                    pass
            if parsed.get("end_date"):
                from datetime import datetime
                try:
                    st.session_state.custom_end_date = datetime.strptime(parsed["end_date"], "%Y-%m-%d").date()
                except Exception:
                    pass
            st.success(f"ProjectMind report successfully loaded: {st.session_state.project_name} v{parsed.get('version')}")
            st.rerun()
            # Other format report
            status_container = st.status("Reconstructing project state...", expanded=True)
            with status_container:
                progress_bar = st.progress(0.0)
                status_container.update(label="Analyzing uploaded document...")
                progress_bar.progress(0.5)
                reconstructed = reconstruct_report_from_text(parsed)
                status_container.update(label="Reconstruction complete!", state="complete", expanded=False)
                progress_bar.progress(1.0)
                st.session_state.project_name = reconstructed.get("project_name", "")
                st.session_state.client_name = reconstructed.get("client_name", "")
                st.session_state.previous_report_data = reconstructed
                st.session_state.report_data = reconstructed
                st.session_state.active_report_meta = None # It's not a saved ProjectMind report yet
                st.warning("The uploaded report is not in ProjectMind format. The project state has been reconstructed using AI, so reconstruction confidence may be lower.")
                st.rerun()

if st.session_state.entry_mode == "Generate New Report" or st.session_state.previous_report_data is not None:
    # 2-column layout for input setup
    left_col, right_col = st.columns(2)
    
    with right_col:
        st.subheader("Project Evidence")
        whatsapp_file = st.file_uploader(
            "WhatsApp Conversation",
            type=["txt"],
            help="Required",
            key="whatsapp_file_uploader"
        )
        supporting_file = st.file_uploader(
            "Supporting Evidence",
            type=["txt"],
            help="Optional. Meeting minutes, call notes, email summaries or status reports.",
            key="supporting_file_uploader"
        )
    
    # File processing and state tracking
    if whatsapp_file is not None:
        if st.session_state.whatsapp_file_name != whatsapp_file.name:
            st.session_state.whatsapp_file_name = whatsapp_file.name
            try:
                whatsapp_text = read_text_file(whatsapp_file)                
                st.session_state.messages = extract_messages(whatsapp_text)
                # Reset state for new file
                st.session_state.report_data = None
                st.session_state.raw_response = ""
                st.session_state.pop("custom_start_date", None)
                st.session_state.pop("custom_end_date", None)
            except Exception as e:
                st.error(f"Error reading WhatsApp file: {str(e)}")
                st.session_state.messages = []
    else:
        # Only reset if we are NOT in a loaded report state
        if st.session_state.whatsapp_file_name is not None and not st.session_state.get("active_report_meta") and not st.session_state.get("previous_report_data"):
            st.session_state.whatsapp_file_name = None
            st.session_state.messages = []
            st.session_state.raw_response = ""
            
    # Track active input states to reset report if they change
    active_supporting_file = supporting_file.name if supporting_file is not None else None
    current_period_key = (
        st.session_state.get("period_selection"),
        st.session_state.get("custom_start_date"),
        st.session_state.get("custom_end_date")
    )
    
    if "prev_supporting_file" not in st.session_state:
        st.session_state.prev_supporting_file = active_supporting_file
    if "prev_period_key" not in st.session_state:
        st.session_state.prev_period_key = current_period_key
    
    if (st.session_state.prev_supporting_file != active_supporting_file or
        st.session_state.prev_period_key != current_period_key):
        # Only reset if not in active_report_meta (loaded from store)
        if not st.session_state.get("active_report_meta"):
            st.session_state.report_data = None
            st.session_state.raw_response = ""
        st.session_state.prev_supporting_file = active_supporting_file
        st.session_state.prev_period_key = current_period_key
    
    with left_col:
        st.subheader("Project Details")
        project_name = st.text_input(
            "Project",
            value=st.session_state.project_name,
            help="The project this report belongs to.",
            key="project_name"
        )
        
        client_name = st.text_input(
            "Client",
            value=st.session_state.client_name,
            help="The client or organisation.",
            key="client_name"
        )
        
        period = st.selectbox(
            "Reporting Period",
            ["Today", "Last 7 Days", "Last 14 Days", "Last 30 Days", "Custom"],
            key="period_selection",
            help="Only conversations inside the selected period will be analysed."
        )

    start_date = None
    end_date = None

    if len(st.session_state.messages) > 0:
        summary = conversation_summary(st.session_state.messages)
        conversation_start = summary["first"].date()
        conversation_end = summary["last"].date()
        
        st.session_state.first_msg_date = conversation_start
        st.session_state.last_msg_date = conversation_end

        today_date = date.today()

        if period == "Today":
            start_date = today_date
            end_date = today_date
        elif period == "Last 7 Days":
            end_date = conversation_end
            start_date = end_date - timedelta(days=7)
        elif period == "Last 14 Days":
            end_date = conversation_end
            start_date = end_date - timedelta(days=14)
        elif period == "Last 30 Days":
            end_date = conversation_end
            start_date = end_date - timedelta(days=30)
        else:
            with left_col:
                col_start, col_end = st.columns(2)
                with col_start:
                    default_start = st.session_state.get("custom_start_date")
                    if default_start is None or default_start < conversation_start or default_start > conversation_end:
                        default_start = conversation_start
                    start_date = st.date_input(
                        "Start Date",
                        value=default_start,
                        min_value=conversation_start,
                        max_value=conversation_end,
                        key="custom_start_date"
                    )
                with col_end:
                    default_end = st.session_state.get("custom_end_date")
                    if default_end is None or default_end < conversation_start or default_end > conversation_end:
                        default_end = conversation_end
                    end_date = st.date_input(
                        "End Date",
                        value=default_end,
                        min_value=conversation_start,
                        max_value=conversation_end,
                        key="custom_end_date"
                    )
    else:
        with left_col:
            st.info("Upload a WhatsApp conversation to define and validate the reporting period.")

    # Display conversation overview inside right column if file uploaded
    if len(st.session_state.messages) > 0:
        with right_col:
            st.subheader("Conversation Overview")
            m_col1, m_col2, m_col3 = st.columns(3)
            summary = conversation_summary(st.session_state.messages)
            conversation_start = summary["first"].date()
            conversation_end = summary["last"].date()
            
            with m_col1:
                st.metric("Messages", summary["count"])
            with m_col2:
                st.metric("First Message", summary["first"].strftime("%d %b %Y"))
            with m_col3:
                st.metric("Last Message", summary["last"].strftime("%d %b %Y"))
                
            st.caption(
                f"Available conversation: {conversation_start.strftime('%d %b %Y')} to {conversation_end.strftime('%d %b %Y')}"
            )
            
            # Conversation Coverage Card (Requirement 6 - Compact)
            st.subheader("Conversation Coverage")
            with st.container(border=True):
                gap_days = (date.today() - conversation_end).days
                if gap_days <= 0:
                    coverage_str = "Up to Date"
                    status_str = "Current"
                    status_color = "green"
                elif gap_days == 1:
                    coverage_str = "Missing Today's Messages"
                    status_str = "Needs Updated Export"
                    status_color = "orange"
                else:
                    coverage_str = f"Outdated by {gap_days} Days"
                    status_str = "Needs Updated Export"
                    status_color = "red"
                    
                freshness = "Current" if gap_days <= 0 else f"{gap_days} day(s) behind today"
                st.markdown(
                    f"• **First message:** {conversation_start.strftime('%d %b %Y')}  \n"
                    f"• **Latest message:** {conversation_end.strftime('%d %b %Y')}  \n"
                    f"• **Data freshness:** {freshness} (Today: {date.today().strftime('%d %b %Y')})  \n"
                    f"• **Coverage status:** <span style='color: {status_color}; font-weight: 500;'>{status_str}</span> ({coverage_str})",
                    unsafe_allow_html=True
                )
            
        # Display Reporting Coverage inside left column to balance page layout heights
        if start_date and end_date:
            coverage = check_coverage(st.session_state.messages, start_date, end_date)
            with left_col:
                st.subheader("Reporting Coverage")
                if coverage["status"] == "AVAILABLE":
                    st.success("Conversation data is available for the selected reporting period.")
                elif coverage["status"] == "PARTIAL":
                    st.warning("Only part of the selected reporting period contains conversation data.")
                else:
                    st.error("No conversation data is available for the selected reporting period.")

# Generate Report Section
st.divider()
generate_disabled = len(st.session_state.messages) == 0
acknowledged = True

if not generate_disabled:
    summary = conversation_summary(st.session_state.messages)
    conversation_end = summary["last"].date()
    today_date = date.today()
    gap_days = (today_date - conversation_end).days
    
    if gap_days > 0:
        warning_msg = f"Latest WhatsApp conversation ends on **{conversation_end.strftime('%d %b %Y')}**. Today's date is **{today_date.strftime('%d %b %Y')}**. A newer WhatsApp export may be available. Some recent work might not be included in this report."
        recommendation_msg = "Please export the latest WhatsApp chat including today's messages for the most accurate report."
        
        if gap_days > 7:
            st.error(f"**CRITICAL WARNING:** {warning_msg}\n\n{recommendation_msg}")
        elif gap_days > 3:
            st.error(f"**HIGH WARNING:** {warning_msg}\n\n{recommendation_msg}")
        elif gap_days > 1:
            st.warning(f"**WARNING (Medium):** {warning_msg}\n\n{recommendation_msg}")
        else:
            st.warning(f"**Warning:** {warning_msg}\n\n{recommendation_msg}")
            
        acknowledged = st.checkbox("Proceed with the current export anyway", value=False, key="freshness_acknowledgement")
        generate_disabled = not acknowledged

if st.button("Generate Report", use_container_width=True, disabled=generate_disabled):
    if not st.session_state.project_name.strip():
        st.error("Please enter a project name.")
    elif not st.session_state.client_name.strip():
        st.error("Please enter a client name.")
    else:
        coverage = check_coverage(st.session_state.messages, start_date, end_date)
        if coverage["status"] == "NO_DATA":
            st.error("No conversation data is available for the selected reporting period.")
        else:
            status_container = st.status("Reading conversation...", expanded=True)
            with status_container:
                progress_bar = st.progress(0.0)
                try:
                    # 1. Reading conversation...
                    progress_bar.progress(0.16)
                    whatsapp_text = ""
                    if whatsapp_file is not None:
                        whatsapp_text = read_text_file(whatsapp_file)
                    
                    # 2. Extracting activities...
                    status_container.update(label="Extracting activities...")
                    progress_bar.progress(0.33)
                    supporting_text = ""
                    if supporting_file is not None:
                        supporting_text = read_text_file(supporting_file)
                    
                    # 3. Matching evidence...
                    status_container.update(label="Matching evidence...")
                    progress_bar.progress(0.50)
                    evidence, filtered_messages = get_combined_evidence(
                        whatsapp_text, start_date, end_date, supporting_text
                    )
                    
                    # 4. Building project intelligence...
                    status_container.update(label="Building project intelligence...")
                    progress_bar.progress(0.66)
                    prompt = build_project_prompt(
                        st.session_state.project_name,
                        st.session_state.client_name,
                        start_date,
                        end_date,
                        evidence,
                        previous_report_data=st.session_state.get("previous_report_data")
                    )
                    
                    # 5. Generating report...
                    status_container.update(label="Generating report...")
                    progress_bar.progress(0.83)
                    report_data, raw_response = analyze_project(prompt)
                    
                    if not isinstance(report_data, dict):
                        st.error("AI did not return a valid report.")
                        st.stop()
                    
                    # 6. Preparing dashboard...
                    status_container.update(label="Preparing dashboard...")
                    progress_bar.progress(1.0)
                    
                    status_container.update(label="Report generated successfully!", state="complete", expanded=False)
                    
                    # Initialize review metadata and verification keys
                    report_data["review_confirmed"] = False
                    report_data["employee_notes"] = ""
                    
                    summary = conversation_summary(st.session_state.messages)
                    last_msg_date_str = summary["last"].strftime("%d %b %Y") if summary["last"] else "Not Available"
                    report_data["latest_conversation_date"] = last_msg_date_str
                    
                    comp_tasks = report_data.get("completed_tasks", [])
                    if isinstance(comp_tasks, list):
                        for t in comp_tasks:
                            if isinstance(t, dict):
                                # If no supporting document was uploaded, force status
                                if supporting_file is None:
                                    t["verification_status"] = "Awaiting Supporting Documents"
                                else:
                                    t["verification_status"] = t.get("verification_status", "Not Verified")
                                
                                # Default User Actions keys
                                t["approval_status"] = "Pending Review"
                                t["employee_notes"] = ""
                                
                                # Phase 1B: time tracking schema
                                t["original_ai_hours"] = t.get("estimated_hours", 0.0)
                                t["time_history"] = [{
                                    "hours": t.get("estimated_hours", 0.0),
                                    "editor": "AI",
                                    "timestamp": _datetime_module.datetime.now().isoformat(),
                                    "reason": "Initial AI estimate"
                                }]
                            
                    st.session_state["report_data"] = report_data
                    st.session_state.raw_response = raw_response
                    
                    # Auto-save report to store
                    from utils import save_report_to_store, set_active_report_in_store
                    persisted = save_report_to_store(
                        project_name=st.session_state.project_name,
                        client_name=st.session_state.client_name,
                        start_date=start_date,
                        end_date=end_date,
                        report_data=report_data,
                        messages=st.session_state.messages
                    )
                    st.session_state.active_report_meta = {
                        "project_id": persisted["project_id"],
                        "version": persisted["version"],
                        "generated_date": persisted["generated_date"],
                        "reporting_period": persisted["reporting_period"]
                    }
                    st.session_state.project_intelligence_engine = persisted.get("project_intelligence_engine")
                    set_active_report_in_store(persisted["project_id"], persisted["version"])
                    # Synchronize state keys to match inputs
                    st.session_state.prev_supporting_file = active_supporting_file
                    st.session_state.prev_period_key = current_period_key
                    
                    # Clear previous widget keys from session state
                    st.session_state.pop("review_confirmed", None)
                    st.session_state.pop("employee_notes", None)
                    for k in list(st.session_state.keys()):
                        if k.startswith("hours_input_") or k.startswith("minutes_input_") or k.startswith("approval_status_") or k.startswith("employee_notes_") or k.startswith("task_name_input_") or k.startswith("reason_input_") or k.startswith("evidence_input_"):
                            st.session_state.pop(k, None)
                            
                    # 7. Report ready
                    status_container.write("Report ready")
                    status_container.update(label="Report generation completed!", state="complete", expanded=False)
                    st.success("Analysis and report generation completed successfully.")
                except Exception as e:
                    status_container.update(label="Report generation failed!", state="error", expanded=True)
                    if "AI generated an invalid response" in str(e):
                        st.error("AI generated an invalid response. Please try again.")
                    else:
                        st.error(f"Report generation failed: {str(e)}")
                    import os
                    path = os.path.join(os.getcwd(), "last_response.txt")
                    if os.path.exists(path):
                        try:
                            with open(path, "r", encoding="utf-8") as f:
                                saved_raw = f.read()
                            with st.expander("Show Raw AI Response"):
                                st.code(saved_raw)
                        except Exception:
                            pass

# Display Project Intelligence Tabs
if st.session_state.report_data is not None:
    st.divider()
    st.header("Project Intelligence")
    
    # Executive Summary Metrics Row
    comp_tasks = st.session_state.report_data.get("completed_tasks", [])
    pend_tasks = st.session_state.report_data.get("pending_tasks", [])
    new_reqs = st.session_state.report_data.get("new_requests", [])
    
    total_hours = sum(float(t.get("estimated_hours", 0) or 0) for t in comp_tasks)
    avg_conf = sum(float(t.get("confidence", 0) or 0) for t in comp_tasks) / len(comp_tasks) if comp_tasks else 0
    
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    with m_col1:
        st.metric("Completed Tasks", len(comp_tasks))
    with m_col2:
        st.metric("Total Time Spent", format_duration(total_hours))
    with m_col3:
        st.metric("Avg AI Assessment", f"{avg_conf:.1f}%")
    with m_col4:
        st.metric("Pending Tasks", len(pend_tasks))
        
    st.write("")
    
    tab_overview, tab_tasks, tab_report, tab_downloads = st.tabs([
        "Overview", "Tasks", "Report", "Downloads"
    ])
    
    # Overview Tab
    with tab_overview:
        import datetime
        # ── Section 1: Project Health ──────────────────────────────────────────
        intel = st.session_state.report_data.get("project_intelligence")
        if intel:
            st.markdown("### Project Intelligence")
            health = intel.get("project_health", {})
            h_status = health.get("status", "On Track")
            h_expl = health.get("explanation", "")
            with st.container(border=True):
                st.markdown("##### Project Health")
                if h_status == "On Track":
                    st.success(f"**{h_status}**: {h_expl}")
                elif h_status == "Needs Attention":
                    st.warning(f"**{h_status}**: {h_expl}")
                elif h_status in ["At Risk", "Blocked"]:
                    st.error(f"**{h_status}**: {h_expl}")
                else:
                    st.info(f"**{h_status}**: {h_expl}")

        # ── Section 2: Intelligence Metrics Grid ──────────────────────────────
        st.write("")
        st.markdown("#### Intelligence Metrics")
        intel_engine = st.session_state.get("project_intelligence_engine") or {}
        if not intel_engine:
            st.info("Project intelligence not available. Generate a report first.")
        else:
            _participants = intel_engine.get("participants", [])
            _pub = intel_engine.get("published_posts", {})
            _approvals = intel_engine.get("approvals", [])
            _followups = intel_engine.get("followups", [])
            _meetings = intel_engine.get("meetings", {})
            _links = intel_engine.get("links", {})
            _pstats = intel_engine.get("participant_stats", {})
            _pdates = intel_engine.get("project_dates", {})

            # Row 1
            r1c1, r1c2, r1c3, r1c4 = st.columns(4)
            with r1c1:
                st.metric("Total Messages", intel_engine.get("total_messages", 0))
            with r1c2:
                st.metric("Participants", len(_participants))
            with r1c3:
                st.metric("Total Posts Published", _pub.get("total_published", 0))
            with r1c4:
                st.metric("Approvals", len(_approvals))

            # Row 2
            r2c1, r2c2, r2c3, r2c4 = st.columns(4)
            with r2c1:
                st.metric("Follow-ups", len(_followups))
            with r2c2:
                st.metric("Meetings", _meetings.get("total_meetings", 0))
            with r2c3:
                docs_shared = _links.get("gdrive", 0) + _links.get("gdocs", 0) + _links.get("documents", 0)
                st.metric("Documents Shared", docs_shared)
            with r2c4:
                st.metric("Most Active Member", _pstats.get("most_active", "N/A"))

            # Row 3
            r3c1, r3c2, r3c3, r3c4 = st.columns(4)
            with r3c1:
                st.metric("Project Duration", f"{_pdates.get('duration_days', 0)} days")
            with r3c2:
                avg_rt = intel_engine.get("average_response_time_minutes", 0)
                st.metric("Avg Response Time", f"{avg_rt} min")
            with r3c3:
                st.metric("Instagram Posts", len(_pub.get("instagram", [])))
            with r3c4:
                st.metric("LinkedIn Posts", len(_pub.get("linkedin", [])))

        # ── Section 3 & 4: AI Insights + Risks + Next Steps ──────────────────
        st.write("")
        if intel:
            messages_list = st.session_state.get("messages", [])
            msg_by_id = {}
            for m in messages_list:
                m_id = m.get("id")
                if m_id:
                    msg_by_id[m_id] = m

            with st.container(border=True):
                col_intel_1, col_intel_2 = st.columns(2)
                with col_intel_1:
                    st.markdown("##### AI Insights")
                    insights = intel.get("insights", [])
                    if not insights:
                        st.write("No insights generated.")
                    else:
                        for i_idx, ins in enumerate(insights):
                            ins_text = ins.get("insight", "")
                            st.write(f"**{i_idx+1}.** {ins_text}")
                            why_list = ins.get("why", [])
                            if why_list:
                                with st.expander("Why?", key=f"why_ins_{i_idx}"):
                                    for w in why_list:
                                        if isinstance(w, str):
                                            m = msg_by_id.get(w)
                                            if m:
                                                m_date = m.get("date")
                                                if isinstance(m_date, str):
                                                    try:
                                                        m_date = datetime.datetime.fromisoformat(m_date)
                                                    except Exception:
                                                        pass
                                                date_str = m_date.strftime("%d %b") if isinstance(m_date, (datetime.datetime, datetime.date)) else str(m_date)
                                                msg_excerpt = m.get("body", "")
                                                if len(msg_excerpt) > 250:
                                                    msg_excerpt = msg_excerpt[:250] + "..."
                                                st.write(f"*{date_str}* | *{m.get('sender', 'System')}*: \"{msg_excerpt}\"")
                                        elif isinstance(w, dict):
                                            m_id = w.get("msg_id") or w.get("id")
                                            m = msg_by_id.get(m_id) if m_id else None
                                            if m:
                                                m_date = m.get("date")
                                                if isinstance(m_date, str):
                                                    try:
                                                        m_date = datetime.datetime.fromisoformat(m_date)
                                                    except Exception:
                                                        pass
                                                date_str = m_date.strftime("%d %b") if isinstance(m_date, (datetime.datetime, datetime.date)) else str(m_date)
                                                msg_excerpt = m.get("body", "")
                                                if len(msg_excerpt) > 250:
                                                    msg_excerpt = msg_excerpt[:250] + "..."
                                                st.write(f"*{date_str}* | *{m.get('sender', 'System')}*: \"{msg_excerpt}\"")
                                            else:
                                                msg_excerpt = w.get("message", "")
                                                if len(msg_excerpt) > 250:
                                                    msg_excerpt = msg_excerpt[:250] + "..."
                                                st.write(f"*{w.get('date', '')}* | *{w.get('sender', '')}*: \"{msg_excerpt}\"")
                            st.write("")

                with col_intel_2:
                    st.markdown("##### Potential Risks")
                    risks = intel.get("potential_risks", [])
                    has_real_risks = False
                    if risks:
                        for rsk in risks:
                            risk_txt = rsk.get("risk", "")
                            if risk_txt and "no significant risks" not in risk_txt.lower():
                                has_real_risks = True
                    if not has_real_risks:
                        st.info("No significant risks detected.")
                    else:
                        for r_idx, rsk in enumerate(risks):
                            risk_txt = rsk.get("risk", "")
                            st.write(f"**{r_idx+1}.** {risk_txt}")
                            why_list = rsk.get("why", [])
                            if why_list:
                                with st.expander("Why?", key=f"why_risk_{r_idx}"):
                                    for w in why_list:
                                        if isinstance(w, str):
                                            m = msg_by_id.get(w)
                                            if m:
                                                m_date = m.get("date")
                                                if isinstance(m_date, str):
                                                    try:
                                                        m_date = datetime.datetime.fromisoformat(m_date)
                                                    except Exception:
                                                        pass
                                                date_str = m_date.strftime("%d %b") if isinstance(m_date, (datetime.datetime, datetime.date)) else str(m_date)
                                                msg_excerpt = m.get("body", "")
                                                if len(msg_excerpt) > 250:
                                                    msg_excerpt = msg_excerpt[:250] + "..."
                                                st.write(f"*{date_str}* | *{m.get('sender', 'System')}*: \"{msg_excerpt}\"")
                                        elif isinstance(w, dict):
                                            m_id = w.get("msg_id") or w.get("id")
                                            m = msg_by_id.get(m_id) if m_id else None
                                            if m:
                                                m_date = m.get("date")
                                                if isinstance(m_date, str):
                                                    try:
                                                        m_date = datetime.datetime.fromisoformat(m_date)
                                                    except Exception:
                                                        pass
                                                date_str = m_date.strftime("%d %b") if isinstance(m_date, (datetime.datetime, datetime.date)) else str(m_date)
                                                msg_excerpt = m.get("body", "")
                                                if len(msg_excerpt) > 250:
                                                    msg_excerpt = msg_excerpt[:250] + "..."
                                                st.write(f"*{date_str}* | *{m.get('sender', 'System')}*: \"{msg_excerpt}\"")
                                            else:
                                                msg_excerpt = w.get("message", "")
                                                if len(msg_excerpt) > 250:
                                                    msg_excerpt = msg_excerpt[:250] + "..."
                                                st.write(f"*{w.get('date', '')}* | *{w.get('sender', '')}*: \"{msg_excerpt}\"")
                            st.write("")

                st.write("")
                st.markdown("##### Recommended Next Steps")
                steps = intel.get("recommended_next_steps", [])
                if steps:
                    for step in steps:
                        st.write(f"- {step}")
                else:
                    st.write("No recommendations generated.")

            st.divider()

        # ── Section 5: Activity Feed ──────────────────────────────────────────
        st.markdown("#### Recent Activity")
        _activity_feed = intel_engine.get("activity_feed", []) if intel_engine else []
        if not _activity_feed:
            # Fallback: build from raw messages
            _raw_msgs = st.session_state.get("messages", [])
            _feed_fallback = []
            for _fm in _raw_msgs:
                _fb = _fm.get("body", "")
                if len(_fb.strip()) > 20:
                    _fd = _fm.get("date")
                    if isinstance(_fd, str):
                        try:
                            _fd = datetime.datetime.fromisoformat(_fd)
                        except Exception:
                            _fd = None
                    if _fd:
                        _feed_fallback.append((_fd, _fm))
            _feed_fallback.sort(key=lambda x: x[0], reverse=True)
            for _fdt, _fmsg in _feed_fallback[:10]:
                _activity_feed.append({
                    "date": _fdt.strftime("%Y-%m-%d"),
                    "sender": _fmsg.get("sender", "System"),
                    "summary": _fmsg.get("body", "").strip()[:120]
                })

        if _activity_feed:
            with st.container(border=True):
                for _ev in _activity_feed:
                    _ev_date = _ev.get("date", "")
                    _ev_sender = _ev.get("sender", "")
                    _ev_summary = _ev.get("summary", "")
                    st.markdown(f"**{_ev_date}** — *{_ev_sender}*: {_ev_summary}")
        else:
            st.info("No recent activity to display.")

        # ── Section 6: Project Summary ────────────────────────────────────────
        st.divider()
        st.subheader("Project Summary")
        st.write(st.session_state.report_data.get("project_summary", ""))

        # ── Section 7: Metadata ───────────────────────────────────────────────
        st.divider()
        st.subheader("Metadata")
        meta_col1, meta_col2, meta_col3 = st.columns(3)
        with meta_col1:
            st.write(f"**Project:** {st.session_state.project_name}")
            st.write(f"**Client:** {st.session_state.client_name}")
        with meta_col2:
            st.write(f"**Period Selection:** {st.session_state.period_selection}")
            if start_date and end_date:
                st.write(f"**Date Range:** {start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}")
        with meta_col3:
            st.write(f"**Completed Tasks:** {len(comp_tasks)}")
            st.write(f"**Pending Tasks:** {len(pend_tasks)}")
            st.write(f"**Client Requests:** {len(new_reqs)}")
            
    # Tasks Tab
    with tab_tasks:
        st.subheader("Completed Tasks")
        if not comp_tasks:
            st.info("No completed tasks identified in this period.")
        else:
            with st.form("edit_tasks_form", clear_on_submit=False):
                for idx, task_item in enumerate(comp_tasks):
                    task_name = task_item.get("task", "Unnamed Task")
                    est_hours = task_item.get("estimated_hours", 0.0)
                    conf = task_item.get("confidence", 0)
                    reason = task_item.get("reason", "")
                    
                    evidence_ids = task_item.get("evidence_ids", [])
                    resolved_evidence = []
                    messages_list = st.session_state.get("messages", [])
                    import datetime
                    
                    msg_by_id = {}
                    for m in messages_list:
                        m_id = m.get("id")
                        if m_id:
                            msg_by_id[m_id] = m
                            
                    for m_id in evidence_ids:
                        m = msg_by_id.get(m_id)
                        if m:
                            m_date = m.get("date")
                            if isinstance(m_date, str):
                                try:
                                    m_date = datetime.datetime.fromisoformat(m_date)
                                except Exception:
                                    pass
                            date_str = m_date.strftime("%d %b %Y") if isinstance(m_date, (datetime.datetime, datetime.date)) else str(m_date)
                            resolved_evidence.append(f"[{m_id}] [{date_str}] {m.get('sender', 'System')}: {m.get('body', '')}")
                            
                    if not resolved_evidence:
                        resolved_evidence = task_item.get("evidence", [])
                        
                    evidence_str = "\n".join(resolved_evidence)
                    
                    # Expander header: Task name, Time, AI Assessment, Verification Status
                    v_status = task_item.get("verification_status", "Awaiting Supporting Documents")
                    expander_title = f"{task_name} ({format_duration(est_hours)} | AI Assessment: {conf}% | Verification: {v_status})"
                    
                    with st.expander(expander_title):
                        # Task and Time spent info
                        st.markdown(f"#### {task_name}")
                        st.markdown(f"**Estimated Time Spent:** {format_duration(est_hours)}")
                        st.markdown(f"**Verification Status:** `{v_status}`")
                        
                        st.divider()
                        
                        # AI Assessment & Why
                        st.markdown("##### AI Assessment")
                        col_conf_1, col_conf_2 = st.columns([1, 4])
                        with col_conf_1:
                            st.metric("Assessment Score", f"{conf}%")
                        with col_conf_2:
                            expl = task_item.get("confidence_explanation", [])
                            if expl:
                                st.write("**Assessment Reasons:**")
                                for item in expl:
                                    st.write(f"- {item}")
                            else:
                                st.write("- Reconstruction complete and consistent based on evidence.")
                                
                        st.divider()
                        
                        # Why? / Reasoning
                        st.markdown("##### Reconstruction Reasoning")
                        st.write(reason)
                        
                        st.divider()
                        
                        # Evidence Panel (Part 5)
                        st.markdown("##### Evidence Panel")
                        if resolved_evidence:
                            for idx_ev, ev in enumerate(resolved_evidence):
                                st.markdown(f"- {ev}")
                        else:
                            st.write("No evidence attached.")
                            
                        st.divider()
                        
                        # User review (notes & approval status)
                        st.markdown("##### User Review & Action")
                        v_col1, v_col2 = st.columns([1, 2])
                        with v_col1:
                            app_status = task_item.get("approval_status", "Pending Review")
                            app_options = ["Pending Review", "Approved", "Rejected"]
                            try:
                                app_idx = app_options.index(app_status)
                            except ValueError:
                                app_idx = 0
                            st.selectbox(
                                "Approve / Reject",
                                options=app_options,
                                index=app_idx,
                                key=f"approval_status_{idx}"
                            )
                        with v_col2:
                            st.text_input(
                                "Employee Notes / Feedback",
                                value=task_item.get("employee_notes", ""),
                                key=f"employee_notes_{idx}"
                            )
                
                # Save Changes Form Submit Button
                save_clicked = st.form_submit_button("Save Changes", use_container_width=True)

                if save_clicked:
                    has_errors = False
                    updated_tasks = []
                    for idx, task_item in enumerate(comp_tasks):
                        # Preserve system-generated values
                        t_name = task_item.get("task", "Unnamed Task")
                        t_hours = task_item.get("estimated_hours", 0.0)
                        t_reason = task_item.get("reason", "")
                        t_conf = task_item.get("confidence", 85)
                        t_conf_expl = task_item.get("confidence_explanation", [])
                        t_ver_status = task_item.get("verification_status", "Awaiting Supporting Documents")
                        t_evidence_ids = task_item.get("evidence_ids", [])
                        t_evidence_raw = task_item.get("evidence", [])

                        # User-editable approval & notes (no hours keys — edited outside form)
                        t_approval = st.session_state[f"approval_status_{idx}"]
                        t_notes = st.session_state[f"employee_notes_{idx}"]

                        updated_tasks.append({
                            "task": t_name,
                            "estimated_hours": t_hours,
                            "original_ai_hours": task_item.get("original_ai_hours", t_hours),
                            "time_history": task_item.get("time_history", []),
                            "confidence": t_conf,
                            "confidence_explanation": t_conf_expl,
                            "verification_status": t_ver_status,
                            "approval_status": t_approval,
                            "employee_notes": t_notes,
                            "reason": t_reason,
                            "evidence": t_evidence_raw,
                            "evidence_ids": t_evidence_ids
                        })

                    if not has_errors:
                        st.session_state.report_data["completed_tasks"] = updated_tasks
                        meta = st.session_state.get("active_report_meta")
                        if meta:
                            from utils import update_report_in_store
                            update_report_in_store(meta["project_id"], meta["version"], st.session_state.report_data)
                        st.success("Changes saved successfully!")
                        st.rerun()

        # ── Phase 2B: Edit Task Times (outside the form) ──────────────────────
        if comp_tasks:
            st.divider()
            st.subheader("Edit Task Times")
            import datetime
            
            @st.dialog("Edit Task Time")
            def show_edit_time_dialog(idx, task_item):
                _task_name = task_item.get("task", "Unnamed Task")
                est_hours = float(task_item.get("estimated_hours", 0.0) or 0.0)
                original_ai_hours = float(task_item.get("original_ai_hours", est_hours) or est_hours)
                
                st.markdown(f"**Task Name:** {_task_name}")
                st.markdown(f"**Original AI Estimate:** {format_duration(original_ai_hours)}")
                st.markdown(f"**Current Estimated Time:** {format_duration(est_hours)}")
                
                _h_default = int(est_hours)
                _m_default = round((est_hours - _h_default) * 60)
                _m_default = (_m_default // 5) * 5
                if _m_default not in list(range(0, 60, 5)):
                    _m_default = 0
                
                te_col1, te_col2 = st.columns(2)
                with te_col1:
                    new_h = st.number_input(
                        "Hours",
                        min_value=0,
                        max_value=999,
                        value=_h_default,
                        step=1,
                        key=f"te_dlg_hours_{idx}"
                    )
                with te_col2:
                    new_m = st.selectbox(
                        "Minutes",
                        options=list(range(0, 60, 5)),
                        index=list(range(0, 60, 5)).index(_m_default) if _m_default in list(range(0, 60, 5)) else 0,
                        key=f"te_dlg_minutes_{idx}"
                    )
                reason_val = st.text_input(
                    "Reason for change (optional)",
                    value="",
                    key=f"te_dlg_reason_{idx}"
                )
                
                st.write("")
                d_col1, d_col2, d_col3 = st.columns(3)
                with d_col1:
                    if st.button("Save", key=f"dlg_save_btn_{idx}", type="primary", use_container_width=True):
                        new_decimal_hours = new_h + new_m / 60.0
                        task_item["estimated_hours"] = new_decimal_hours
                        if "time_history" not in task_item:
                            task_item["time_history"] = []
                        task_item["time_history"].append({
                            "hours": new_decimal_hours,
                            "editor": st.session_state.get("project_name", "Employee"),
                            "timestamp": datetime.datetime.now().isoformat(),
                            "reason": reason_val
                        })
                        meta = st.session_state.get("active_report_meta")
                        if meta:
                            from utils import update_report_in_store
                            update_report_in_store(meta["project_id"], meta["version"], st.session_state.report_data)
                        st.success("Time updated.")
                        st.rerun()
                with d_col2:
                    if st.button("Cancel", key=f"dlg_cancel_btn_{idx}", use_container_width=True):
                        st.rerun()
                with d_col3:
                    if st.button("Close", key=f"dlg_close_btn_{idx}", use_container_width=True):
                        st.rerun()
                
                # Time History inside the dialog
                _hist = task_item.get("time_history", [])
                if _hist:
                    st.divider()
                    st.markdown("**Time History**")
                    for _he in _hist:
                        _he_ts = _he.get("timestamp", "")
                        _he_h = _he.get("hours", 0.0)
                        _he_ed = _he.get("editor", "")
                        _he_r = _he.get("reason", "")
                        st.markdown(
                            f"- **{format_duration(_he_h)}** by *{_he_ed}* on `{_he_ts[:19]}` — {_he_r}"
                        )
            
            # Render task list with trigger buttons
            for idx, task_item in enumerate(comp_tasks):
                _task_name = task_item.get("task", "Unnamed Task")
                est_hours = float(task_item.get("estimated_hours", 0.0) or 0.0)
                
                t_row_col1, t_row_col2 = st.columns([7.5, 2.5])
                with t_row_col1:
                    st.markdown(f"**{_task_name}** ({format_duration(est_hours)})")
                with t_row_col2:
                    if st.button("Edit Time", key=f"edit_time_trigger_{idx}", use_container_width=True):
                        show_edit_time_dialog(idx, task_item)
                        
        st.divider()
        st.subheader("Pending Tasks")
        if not pend_tasks:
            st.info("No pending tasks identified.")
        else:
            for pt in pend_tasks:
                st.write(f"- {pt}")
                
        st.divider()
        st.subheader("Client Requests")
        if not new_reqs:
            st.info("No client requests identified.")
        else:
            for nr in new_reqs:
                st.write(f"- {nr}")
                
        st.divider()
        st.subheader("Employee Review")
        st.checkbox(
            "Review Confirmed",
            value=st.session_state.report_data.get("review_confirmed", False),
            key="review_confirmed"
        )
        st.subheader("Employee Notes")
        st.text_area(
            "Employee Notes",
            label_visibility="collapsed",
            value=st.session_state.report_data.get("employee_notes", ""),
            key="employee_notes"
        )
                
    # Report Tab
    with tab_report:
        st.subheader("Client Report")
        client_report = st.session_state.report_data.get("client_report", "")
        if client_report:
            st.markdown(client_report)
        else:
            st.info("No report generated.")
        
    # Downloads Tab
    with tab_downloads:
        st.subheader("Available Downloads")
        
        safe_proj_name = "".join(c for c in st.session_state.project_name if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
        safe_client_name = "".join(c for c in st.session_state.client_name if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
        if not safe_proj_name:
            safe_proj_name = "project"
        if not safe_client_name:
            safe_client_name = "client"
            
        excel_filename = f"{safe_proj_name}_{safe_client_name}_Intelligence.xlsx"
        word_filename = f"{safe_proj_name}_{safe_client_name}_Report.docx"
        json_filename = f"{safe_proj_name}_{safe_client_name}_Intelligence.json"
        
        # Generate binaries in real-time based on updated st.session_state.report_data
        _report_version = st.session_state.get("active_report_meta", {}).get("version") if st.session_state.get("active_report_meta") else None
        excel_data = generate_excel_report(st.session_state.report_data, report_version=_report_version)
        word_data = generate_word_report(
            st.session_state.project_name,
            st.session_state.client_name,
            start_date,
            end_date,
            st.session_state.report_data,
            report_version=_report_version
        )
        
        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            st.download_button(
                label="Download Word Report (DOCX)",
                data=word_data,
                file_name=word_filename,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True
            )
        with dl_col2:
            st.download_button(
                label="Download Excel Timesheet (XLSX)",
                data=excel_data,
                file_name=excel_filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            
        st.write("")
        with st.expander("Developer Options"):
            json_str = json.dumps(st.session_state.report_data, indent=2)
            st.download_button(
                label="Download Raw Intelligence JSON",
                data=json_str,
                file_name=json_filename,
                mime="application/json",
                use_container_width=True
            )
            st.code(json_str, language="json")  
