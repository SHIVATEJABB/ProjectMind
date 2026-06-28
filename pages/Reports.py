import streamlit as st
st.set_page_config(page_title="ProjectMind", page_icon="assets/favicon.png", layout="wide", initial_sidebar_state="expanded")

from session import initialize_session_state
initialize_session_state()

st.markdown(
    f"<div style='color: gray; font-size: 0.9em; margin-bottom: 10px;'>"
    f"Reports"
    f"</div>",
    unsafe_allow_html=True
)

from collections import defaultdict
import datetime

from utils import (
    list_reports_from_store,
    load_report_from_store,
    delete_report_from_store,
    generate_excel_report,
    generate_word_report,
)

# Handle view details page state
if "view_report_details" not in st.session_state:
    st.session_state.view_report_details = None

reports = list_reports_from_store()

# Calculate dynamic summary metrics
projects = set()
total_reports = 0
total_completed_tasks = 0
total_pending_tasks = 0
total_hours_logged = 0.0
generated_today_count = 0

today_str = datetime.date.today().strftime("%Y-%m-%d")

for r in reports:
    projects.add(r["project_id"])
    total_reports += 1
    
    r_data = r.get("report_data", {})
    comp = r_data.get("completed_tasks", [])
    total_completed_tasks += len(comp)
    total_pending_tasks += len(r_data.get("pending_tasks", []))
    
    for t in comp:
        if isinstance(t, dict):
            total_hours_logged += t.get("estimated_hours", 0.0)
            
    if r.get("generated_date") == today_str:
        generated_today_count += 1

# If viewing details of a report (Part 14)
if st.session_state.view_report_details is not None:
    report = st.session_state.view_report_details
    r_data = report["report_data"]
    v = report["version"]
    
    # Format generated date
    try:
        gen_d = datetime.datetime.strptime(report["generated_date"], "%Y-%m-%d").strftime("%d %b %Y")
    except Exception:
        gen_d = report["generated_date"]
        
    st.title("Report Details")
    st.markdown(f"### {report['project_name']} (Version {v})")
    
    # Back to Reports Button
    if st.button("Back to Reports", key="back_to_reports_from_details"):
        st.session_state.view_report_details = None
        st.rerun()
        
    with st.container(border=True):
        st.write(f"**Client:** {report['client_name']}")
        st.write(f"**Reporting Period:** {report.get('reporting_period', 'Not Specified')}")
        st.write(f"**Generated:** {gen_d}")
        
    st.write("")
    st.markdown("#### Project Summary")
    st.write(r_data.get("project_summary", ""))
    
    st.write("")
    st.markdown("#### Completed Tasks")
    comp_tasks = r_data.get("completed_tasks", [])
    if comp_tasks:
        for idx, t in enumerate(comp_tasks):
            if isinstance(t, dict):
                with st.container(border=True):
                    task_name = t.get('task', '')
                    est_hours = t.get('estimated_hours', 0.0)
                    conf = t.get('confidence', 0)
                    v_status = t.get('verification_status', 'Awaiting Supporting Documents')
                    app_status = t.get('approval_status', 'Pending Review')
                    from utils import format_duration
                    st.markdown(f"**{idx+1}. {task_name}**")
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        st.write(f"**Time Spent:** {format_duration(est_hours)}")
                    with col_b:
                        st.write(f"**AI Assessment:** {conf}%")
                    with col_c:
                        st.write(f"**Verification:** {v_status}")
                    st.write(f"**Approval:** {app_status}")
                    notes = t.get('employee_notes', '')
                    if notes:
                        st.write(f"**Employee Notes:** {notes}")
                    reason = t.get('reason', '')
                    if reason:
                        with st.expander("Reasoning"):
                            st.write(reason)
                    # Resolve evidence from IDs
                    evidence_ids = t.get("evidence_ids", [])
                    resolved_evidence = []
                    report_messages = report.get("messages", [])
                    msg_by_id = {m.get("id"): m for m in report_messages if m.get("id")}
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
                            resolved_evidence.append(f"[{date_str}] {m.get('sender', 'System')}: {m.get('body', '')}")
                    if not resolved_evidence:
                        resolved_evidence = t.get("evidence", [])
                    if resolved_evidence:
                        with st.expander("Evidence"):
                            for ev in resolved_evidence:
                                st.write(f"- {ev}")
                    # Time History
                    time_history = t.get("time_history", [])
                    if len(time_history) > 1:
                        with st.expander("Time History"):
                            for entry in time_history:
                                h_hours = entry.get("hours", 0)
                                h_editor = entry.get("editor", "Unknown")
                                h_ts = entry.get("timestamp", "")
                                h_reason = entry.get("reason", "")
                                ts_str = ""
                                if h_ts:
                                    try:
                                        ts_str = datetime.datetime.fromisoformat(h_ts).strftime("%d %b %Y %H:%M")
                                    except Exception:
                                        ts_str = h_ts
                                st.write(f"- **{h_editor}** set {format_duration(h_hours)}{' — ' + h_reason if h_reason else ''}{' (' + ts_str + ')' if ts_str else ''}")
    else:
        st.write("None")
        
    st.write("")
    st.markdown("#### Pending Tasks")
    pend_tasks = r_data.get("pending_tasks", [])
    if pend_tasks:
        for pt in pend_tasks:
            st.write(f"- {pt}")
    else:
        st.write("None")
        
    st.write("")
    st.markdown("#### Client Requests")
    new_reqs = r_data.get("new_requests", [])
    if new_reqs:
        for nr in new_reqs:
            st.write(f"- {nr}")
    else:
        st.write("None")
        
    st.write("")
    st.markdown("#### Client Report")
    st.markdown(r_data.get("client_report", "No report text."))

else:
    # Main Project Library Page
    st.title("Project Library")
    st.caption("Browse, view, export, and continue reporting on all local project records.")
    
    # 1. Reports Overview metrics (Part 11)
    if reports:
        st.write("")
        m_col1, m_col2, m_col3, m_col4, m_col5, m_col6 = st.columns(6)
        m_col1.metric("Projects", len(projects))
        m_col2.metric("Reports", total_reports)
        m_col3.metric("Completed Tasks", total_completed_tasks)
        m_col4.metric("Pending Tasks", total_pending_tasks)
        m_col5.metric("Hours Logged", f"{total_hours_logged:.1f}")
        m_col6.metric("Generated Today", generated_today_count)
        st.write("")

    # 2. Empty State (Part 12)
    if not reports:
        st.info("No reports have been generated yet.")
        if st.button("Generate First Report", use_container_width=True):
            st.switch_page("pages/Dashboard.py")
    else:
        # Group reports by project_id
        grouped = defaultdict(list)
        for r in reports:
            grouped[r["project_id"]].append(r)
            
        for pid, version_list in grouped.items():
            # Sort version list descending (latest first) to fetch latest metadata
            sorted_desc = sorted(version_list, key=lambda x: x["version"], reverse=True)
            latest = sorted_desc[0]
            
            p_name = latest["project_name"]
            c_name = latest["client_name"]
            total_r = len(version_list)
            
            # Format Last Updated date
            last_gen_raw = latest["generated_date"]
            if last_gen_raw == today_str:
                last_updated = "Today"
            else:
                try:
                    last_updated = datetime.datetime.strptime(last_gen_raw, "%Y-%m-%d").strftime("%d %b %Y")
                except Exception:
                    last_updated = last_gen_raw
                    
            latest_period = latest.get("reporting_period", "Not Specified")
            
            # Draw Project Card Container (Part 3)
            with st.container(border=True):
                col_n, col_d, col_p = st.columns([2, 1, 2])
                with col_n:
                    st.markdown(f"### {p_name}")
                    st.write(f"**Client:** {c_name}")
                with col_d:
                    st.write(f"**Reports:** {total_r}")
                    st.write(f"**Last Updated:** {last_updated}")
                with col_p:
                    st.write(f"**Latest Report:**")
                    st.write(latest_period)
                    
                st.write("")
                
                # Render Timeline (Part 10)
                st.markdown("**Timeline**")
                sorted_asc = sorted(version_list, key=lambda x: x["version"])
                timeline_elements = []
                for r in sorted_asc:
                    period_str = r.get("reporting_period", "")
                    end_date_str = ""
                    if " to " in period_str:
                        try:
                            end_d = period_str.split(" to ")[1]
                            end_date_str = datetime.datetime.strptime(end_d, "%Y-%m-%d").strftime("%d %b %Y")
                        except Exception:
                            end_date_str = r.get("generated_date", "")
                    else:
                        end_date_str = r.get("generated_date", "")
                        
                    timeline_elements.append(f"{end_date_str}  \n**Report v{r['version']}**")
                
                # Join timeline elements with clean vertical arrow separator
                st.markdown("\n\n↓\n\n".join(timeline_elements))
                st.write("")
                
                # Expandable card version view (Part 4)
                with st.expander("View Reports"):
                    for report in sorted_desc:
                        v = report["version"]
                        gen_date_raw = report["generated_date"]
                        try:
                            gen_d_str = datetime.datetime.strptime(gen_date_raw, "%Y-%m-%d").strftime("%d %b %Y")
                        except Exception:
                            gen_d_str = gen_date_raw
                            
                        p_str = report.get("reporting_period", "")
                        
                        col_ver_info, col_ver_actions = st.columns([1, 4])
                        
                        with col_ver_info:
                            st.write(f"**Report v{v}**")
                            st.caption(f"Generated: {gen_d_str} | Period: {p_str}")
                            
                        with col_ver_actions:
                            # Grouped report actions
                            col_primary, col_export, col_danger = st.columns([3.5, 1.8, 0.7])
                            
                            # 1. Primary Actions (View Details, Continue, Ask Chitti)
                            with col_primary:
                                pca1, pca2, pca3 = st.columns(3)
                                with pca1:
                                    if st.button("View Details", key=f"view_{pid}_v{v}", use_container_width=True):
                                        st.session_state.view_report_details = report
                                        st.rerun()
                                with pca2:
                                    if st.button("Continue", key=f"cont_{pid}_v{v}", use_container_width=True):
                                        st.session_state.project_name = report["project_name"]
                                        st.session_state.client_name = report["client_name"]
                                        st.session_state.previous_report_data = report["report_data"]
                                        st.session_state.report_data = report["report_data"]
                                        st.session_state.project_intelligence_engine = report.get("project_intelligence_engine")
                                        st.session_state.active_report_meta = {
                                            "project_id": pid,
                                            "version": v,
                                            "generated_date": report["generated_date"],
                                            "reporting_period": report.get("reporting_period", "")
                                        }
                                        if "messages" in report:
                                            st.session_state.messages = report["messages"]
                                        st.session_state.entry_mode = "Continue From Existing Report"
                                        
                                        # Restore dates
                                        if report.get("start_date"):
                                            try:
                                                st.session_state.custom_start_date = datetime.datetime.strptime(report["start_date"], "%Y-%m-%d").date()
                                            except Exception:
                                                pass
                                        if report.get("end_date"):
                                            try:
                                                st.session_state.custom_end_date = datetime.datetime.strptime(report["end_date"], "%Y-%m-%d").date()
                                            except Exception:
                                                pass
                                                
                                        from utils import set_active_report_in_store
                                        set_active_report_in_store(pid, v)
                                        st.switch_page("pages/Dashboard.py")
                                with pca3:
                                    if st.button("Ask Chitti", key=f"ask_{pid}_v{v}", use_container_width=True):
                                        st.session_state.report_data = report["report_data"]
                                        st.session_state.project_name = report["project_name"]
                                        st.session_state.client_name = report["client_name"]
                                        st.session_state.project_intelligence_engine = report.get("project_intelligence_engine")
                                        st.session_state.active_report_meta = {
                                            "project_id": pid,
                                            "version": v,
                                            "generated_date": report["generated_date"],
                                            "reporting_period": report.get("reporting_period", "")
                                        }
                                        if "messages" in report:
                                            st.session_state.messages = report["messages"]
                                        from utils import set_active_report_in_store
                                        set_active_report_in_store(pid, v)
                                        st.switch_page("pages/Ask_Chitti.py")
                                        
                            # 2. Export Actions (Word, Excel)
                            with col_export:
                                eca1, eca2 = st.columns(2)
                                with eca1:
                                    try:
                                        s_dt = datetime.datetime.strptime(report.get("start_date", ""), "%Y-%m-%d").date() if report.get("start_date") else None
                                        e_dt = datetime.datetime.strptime(report.get("end_date", ""), "%Y-%m-%d").date() if report.get("end_date") else None
                                    except Exception:
                                        s_dt = None
                                        e_dt = None
                                        
                                    word_data = generate_word_report(
                                        report["project_name"],
                                        report["client_name"],
                                        s_dt,
                                        e_dt,
                                        report["report_data"],
                                        report_version=v
                                    )
                                    safe_p = "".join(c for c in report["project_name"] if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
                                    st.download_button(
                                        label="Word",
                                        data=word_data,
                                        file_name=f"{safe_p}_Report_v{v}.docx",
                                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                        key=f"word_{pid}_v{v}",
                                        use_container_width=True
                                    )
                                with eca2:
                                    excel_data = generate_excel_report(report["report_data"], report_version=v)
                                    st.download_button(
                                        label="Excel",
                                        data=excel_data,
                                        file_name=f"{safe_p}_Timesheet_v{v}.xlsx",
                                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                        key=f"excel_{pid}_v{v}",
                                        use_container_width=True
                                    )
                                    
                            # 3. Danger Action (Delete)
                            with col_danger:
                                if st.button("Delete", key=f"del_{pid}_v{v}", use_container_width=True):
                                    st.session_state[f"confirm_delete_{pid}_v{v}"] = True
                                    st.rerun()
                                    
                        # Unified confirmation banner if delete was clicked
                        if st.session_state.get(f"confirm_delete_{pid}_v{v}"):
                            st.write("")
                            with st.container(border=True):
                                st.warning(f"Are you sure you want to permanently delete Report v{v}?")
                                dc1, dc2 = st.columns(2)
                                with dc1:
                                    if st.button("Yes, Delete", key=f"yes_del_{pid}_v{v}", use_container_width=True, type="primary"):
                                        delete_report_from_store(pid, v)
                                        curr_meta = st.session_state.get("active_report_meta")
                                        if curr_meta and curr_meta["project_id"] == pid and curr_meta["version"] == v:
                                            # Clear active project state keys
                                            st.session_state.report_data = None
                                            st.session_state.active_report_meta = None
                                            st.session_state.project_name = ""
                                            st.session_state.client_name = ""
                                            st.session_state.previous_report_data = None
                                            st.session_state.chat_history = []
                                            st.session_state.messages = []
                                            st.session_state.project_intelligence_engine = None
                                            st.session_state.selected_project = None
                                            st.session_state.selected_report = None
                                            st.session_state.selected_report_id = None
                                            from utils import clear_active_report_in_store
                                            clear_active_report_in_store()
                                            st.session_state[f"confirm_delete_{pid}_v{v}"] = False
                                            st.switch_page("pages/Reports.py")
                                        else:
                                            st.session_state[f"confirm_delete_{pid}_v{v}"] = False
                                            st.rerun()
                                with dc2:
                                    if st.button("Cancel", key=f"cancel_del_{pid}_v{v}", use_container_width=True):
                                        st.session_state[f"confirm_delete_{pid}_v{v}"] = False
                                        st.rerun()
                                    
                        st.write("")
            st.write("")