import streamlit as st
st.set_page_config(page_title="Ask Chitti", layout="wide")

from session import initialize_session_state
initialize_session_state()

import json
import re
import datetime
from config import client, MODEL_NAME


def matches_query_only(msg, query):
    q = query.strip().lower()
    body = msg.get("body", "").lower()
    sender = msg.get("sender", "").lower()
    dt = msg.get("date")
    
    # 1. Keyword search (case-insensitive in body or sender)
    if q in body or q in sender:
        return True
        
    # 2. Date search (e.g., "19 June", "2026-06-19", etc.)
    if dt:
        formats = [
            dt.strftime("%d %b %Y").lower(),  # "19 jun 2026"
            dt.strftime("%d %B %Y").lower(),  # "19 june 2026"
            dt.strftime("%Y-%m-%d").lower(),  # "2026-06-19"
            dt.strftime("%d/%m/%y").lower(),  # "19/06/26"
            dt.strftime("%d/%m/%Y").lower(),  # "19/06/2026"
            dt.strftime("%b %d").lower(),     # "jun 19"
            dt.strftime("%B %d").lower()      # "june 19"
        ]
        if any(q in fmt for fmt in formats):
            return True
            
    # 3. Attachment search
    attachment_keywords = ["pdf", "image", "video", "link", "canva", "google drive", "drive"]
    if q in attachment_keywords:
        if q == "pdf" and (".pdf" in body or "pdf" in body or "<attached:" in body):
            return True
        if q == "image" and any(x in body for x in ["image", "photo", ".jpg", ".jpeg", ".png", "<attached:"]):
            return True
        if q == "video" and any(x in body for x in ["video", ".mp4", ".mov", ".avi"]):
            return True
        if q == "link" and any(x in body for x in ["http://", "https://", "www.", ".com", ".org", ".co"]):
            return True
        if q == "canva" and "canva" in body:
            return True
        if q in ["google drive", "drive"] and any(x in body for x in ["drive.google.com", "google drive", "docs.google.com"]):
            return True
            
    return False


def retrieve_relevant_messages(question, messages_list):
    if not messages_list:
        return "", 0
        
    q_lower = question.strip().lower()
    
    # 1. Quoted text extraction
    quotes = re.findall(r'"([^"]*)"', question) + re.findall(r"'([^']*)'", question)
    
    # 2. Keyword parsing (stop words removal)
    stop_words = {
        "who", "what", "when", "where", "why", "how", "is", "was", "were", "are", 
        "the", "a", "an", "and", "or", "but", "to", "for", "on", "in", "at", "by", 
        "show", "me", "find", "search", "about", "project", "report", "question", 
        "request", "requested", "change", "changed", "schedule", "scheduled", 
        "meeting", "link", "links", "instagram", "post", "url", "of", "with", "have", "had", "has", "do", "does", "did"
    }
    
    words = re.findall(r'\b\w+\b', q_lower)
    keywords = [w for w in words if w not in stop_words and len(w) > 1]
    
    # 3. Score each message
    scored_messages = []
    
    for idx, msg in enumerate(messages_list):
        score = 0
        body = msg.get("body", "").lower()
        sender = msg.get("sender", "").lower()
        dt = msg.get("date")
        
        # Check quoted text
        for quote in quotes:
            quote_clean = quote.strip().lower()
            if quote_clean and quote_clean in body:
                score += 25
                
        # URL/Attachment check
        if any(kw in q_lower for kw in ["link", "url", "instagram", "website"]):
            if any(link_indicator in body for link_indicator in ["http://", "https://", "www.", ".com", ".org", "instagram.com"]):
                score += 20
                
        # Sender check
        for w in keywords:
            if w in sender:
                score += 15
                
        # Date check
        if dt:
            months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
                      "january", "february", "march", "april", "june", "july", "august", "september", "october", "november", "december"]
            for month in months:
                if month in q_lower and month in dt.strftime("%B").lower():
                    score += 15
            day_num = str(dt.day)
            digits = re.findall(r'\b\d+\b', q_lower)
            if day_num in digits:
                score += 15
                
        # Keyword match
        for kw in keywords:
            if kw in body:
                score += 10
                if re.search(rf'\b{kw}\b', body):
                    score += 5
                    
        # Token overlap
        body_words = set(re.findall(r'\b\w+\b', body))
        overlap = len(set(keywords).intersection(body_words))
        score += overlap * 2
        
        if score > 0:
            scored_messages.append((score, idx))
            
    if not scored_messages:
        return "", 0
        
    scored_messages.sort(key=lambda x: x[0], reverse=True)
    
    # Return top 15 matches
    top_matches = scored_messages[:15]
    
    # Collect indices with surrounding +/- 2 context
    context_indices = set()
    for score, idx in top_matches:
        for offset in range(-2, 3):
            target_idx = idx + offset
            if 0 <= target_idx < len(messages_list):
                context_indices.add(target_idx)
                
    sorted_indices = sorted(list(context_indices))
    
    # Construct context string
    context_lines = []
    prev_idx = -1
    
    for idx in sorted_indices:
        msg = messages_list[idx]
        sender = msg.get("sender", "System")
        dt = msg.get("date")
        date_str = dt.strftime("%d %b %Y") if dt else "Unknown"
        time_str = dt.strftime("%I:%M %p") if dt else "Unknown"
        body = msg.get("body", "")
        
        if prev_idx != -1 and idx > prev_idx + 1:
            context_lines.append("--- [Conversation Gap] ---")
            
        context_lines.append(f"[{date_str} {time_str}] {sender}: {body}")
        prev_idx = idx
        
    context_str = "\n".join(context_lines)
    return context_str, top_matches[0][0]


def get_messages_for_day(question, messages_list):
    if not messages_list:
        return None, None
        
    q = question.lower()
    target_date = None
    
    # 1. Check "yesterday"
    if "yesterday" in q:
        target_date = datetime.date.today() - datetime.timedelta(days=1)
    else:
        # Check month name and day number
        months_map = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
            "january": 1, "february": 2, "march": 3, "april": 4, "june": 6, "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12
        }
        found_month = None
        for m_name, m_val in months_map.items():
            if m_name in q:
                found_month = m_val
                break
                
        if found_month:
            digits = re.findall(r'\b\d+\b', q)
            if digits:
                day = int(digits[0])
                year = datetime.date.today().year
                last_dt = messages_list[-1].get("date")
                if last_dt:
                    year = last_dt.year
                try:
                    target_date = datetime.date(year, found_month, day)
                except Exception:
                    pass
                    
    if target_date:
        filtered = []
        for msg in messages_list:
            dt = msg.get("date")
            if dt and dt.date() == target_date:
                filtered.append(msg)
        return filtered, target_date
        
    return None, None


def route_and_answer_question(q, intel):
    """
    Analyzes the query and routes it to a deterministic intelligence answer if factual.
    Returns (answer_text, was_factual)
    """
    import re
    q_lower = q.lower().strip()
    
    is_timeline = any(k in q_lower for k in ["busiest", "busy days", "active days", "timeline", "message frequency"])
    is_member_stats = any(k in q_lower for k in ["most active", "least active", "who was active", "who sent", "active member", "who sent most", "most messages"])
    is_participants = any(k in q_lower for k in ["participant", "member", "people", "who is in", "who are the", "participants", "team members", "who is on", "who is in the project"])
    is_linkedin = any(k in q_lower for k in ["linkedin post", "linkedin url", "linkedin link", "linkedin posts", "linkedin"])
    is_instagram = any(k in q_lower for k in ["instagram post", "instagram url", "instagram link", "instagram posts", "instagram"])
    is_facebook = any(k in q_lower for k in ["facebook post", "facebook url", "facebook link", "facebook posts", "facebook"])
    is_twitter = any(k in q_lower for k in ["twitter post", "twitter url", "twitter link", "tweet", "tweets", "twitter posts", "x.com post", "twitter"])
    is_posts = any(k in q_lower for k in ["published post", "how many posts", "published links", "posts published", "total posts"])
    is_approvals = any(k in q_lower for k in ["approval", "approve", "approved", "approvals", "how many approvals", "total approvals"])
    is_followups = any(k in q_lower for k in ["follow-up", "followup", "follow up", "reminder", "updates", "follow-ups", "followups", "following up", "how many followups"])
    is_meetings = any(k in q_lower for k in ["meeting", "zoom", "meet", "teams", "google meet", "calendar", "meetings", "how many meetings", "total meetings"])
    is_docs = any(k in q_lower for k in ["document", "file", "drive", "canva", "gdocs", "image", "video", "media", "documents", "how many documents", "files shared", "pdfs"])
    is_msg_count = any(k in q_lower for k in ["exchanged", "how many messages", "message count", "total messages", "messages"])
    is_duration = any(k in q_lower for k in ["duration", "how long", "project period", "start date", "end date", "project duration", "how many days"])
    is_avg_response = any(k in q_lower for k in ["average response", "response time", "avg response", "how fast"])

    is_factual = any([
        is_timeline, is_member_stats, is_participants, is_linkedin, is_instagram,
        is_facebook, is_twitter, is_posts, is_approvals, is_followups, is_meetings,
        is_docs, is_msg_count, is_duration, is_avg_response
    ])
    
    if not is_factual:
        return None, False
        
    if not intel:
        return "This information is not available in the current project data.", True

    if is_timeline:
        activity = intel.get("activity", {})
        if not activity:
            return "No daily activity data found.", True
        sorted_act = sorted(activity.items(), key=lambda x: x[1], reverse=True)
        lines = ["#### Daily Message Activity (Busiest Days First)", ""]
        for date_str, count in sorted_act[:10]:
            lines.append(f"- **{date_str}**: {count} messages")
        return "\n".join(lines), True

    elif is_avg_response:
        avg = intel.get("average_response_time_minutes", 0)
        if not avg:
            return "No average response time detected in this project's conversation.", True
        return f"**Average response time:** {avg} minutes", True

    elif is_member_stats:
        stats = intel.get("participant_stats", {})
        m_per_p = stats.get("messages_per_participant", {})
        most = stats.get("most_active", "N/A")
        least = stats.get("least_active", "N/A")
        most_count = m_per_p.get(most, 0) if most != "N/A" else 0
        lines = [
            "#### Participant Activity Stats",
            f"- **Most Active Member:** {most}" + (f" ({most_count} messages)" if most_count else ""),
            f"- **Least Active Member:** {least}",
            "",
            "**Message Breakdown:**"
        ]
        if m_per_p:
            for p, count in sorted(m_per_p.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"- {p}: {count} messages")
        else:
            lines.append("No participant message breakdown available.")
        return "\n".join(lines), True

    elif is_participants:
        parts = intel.get("participants", [])
        if not parts:
            return "No participants identified in this project's conversation.", True
        lines = ["#### Project Participants", ""]
        for p in parts:
            lines.append(f"- {p}")
        return "\n".join(lines), True

    elif is_linkedin:
        pub = intel.get("published_posts", {})
        urls = pub.get("linkedin", [])
        lines = [f"#### LinkedIn Published Posts ({len(urls)} posts)", ""]
        if urls:
            for url in urls:
                lines.append(f"- [{url}]({url})")
        else:
            lines.append("No LinkedIn posts detected in this project's conversation.")
        return "\n".join(lines), True

    elif is_instagram:
        pub = intel.get("published_posts", {})
        urls = pub.get("instagram", [])
        lines = [f"#### Instagram Published Posts ({len(urls)} posts)", ""]
        if urls:
            for url in urls:
                lines.append(f"- [{url}]({url})")
        else:
            lines.append("No Instagram posts detected in this project's conversation.")
        return "\n".join(lines), True

    elif is_facebook:
        pub = intel.get("published_posts", {})
        urls = pub.get("facebook", [])
        lines = [f"#### Facebook Published Posts ({len(urls)} posts)", ""]
        if urls:
            for url in urls:
                lines.append(f"- [{url}]({url})")
        else:
            lines.append("No Facebook posts detected in this project's conversation.")
        return "\n".join(lines), True

    elif is_twitter:
        pub = intel.get("published_posts", {})
        urls = pub.get("twitter", [])
        lines = [f"#### Twitter/X Published Posts ({len(urls)} posts)", ""]
        if urls:
            for url in urls:
                lines.append(f"- [{url}]({url})")
        else:
            lines.append("No Twitter/X posts detected in this project's conversation.")
        return "\n".join(lines), True

    elif is_posts:
        pub = intel.get("published_posts", {})
        tot = pub.get("total_published", 0)
        lines = [
            f"#### Total Published Posts ({tot} posts)",
            f"- **Instagram:** {len(pub.get('instagram', []))}",
            f"- **LinkedIn:** {len(pub.get('linkedin', []))}",
            f"- **Facebook:** {len(pub.get('facebook', []))}",
            f"- **Twitter/X:** {len(pub.get('twitter', []))}",
            ""
        ]
        has_any = False
        for platform, urls in [("Instagram", pub.get("instagram", [])),
                               ("LinkedIn", pub.get("linkedin", [])),
                               ("Facebook", pub.get("facebook", [])),
                               ("Twitter/X", pub.get("twitter", []))]:
            if urls:
                has_any = True
                lines.append(f"**{platform} URLs:**")
                for url in urls:
                    lines.append(f"- [{url}]({url})")
        if not has_any:
            lines.append("No published posts detected in this project's conversation.")
        return "\n".join(lines), True

    elif is_approvals:
        approvals = intel.get("approvals", [])
        lines = [f"#### Client Approvals Detected ({len(approvals)})", ""]
        if approvals:
            for idx, app in enumerate(approvals[:3]):
                lines.append(f"**{idx+1}. Approval on {app.get('date', '')}**")
                lines.append(f"- **Sender:** {app.get('sender', 'System')}")
                lines.append(f"- **Message excerpt:** \"{app.get('message', '')}\"")
                lines.append("")
            if len(approvals) > 3:
                lines.append(f"_...and {len(approvals) - 3} more approval(s)._")
        else:
            lines.append("No approvals detected in this project's conversation.")
        return "\n".join(lines), True

    elif is_followups:
        followups = intel.get("followups", [])
        lines = [f"#### Follow-ups Sent ({len(followups)})", ""]
        if followups:
            for idx, f in enumerate(followups[:3]):
                lines.append(f"**{idx+1}. Follow-up on {f.get('date', '')}**")
                lines.append(f"- **Sender:** {f.get('sender', 'System')}")
                lines.append(f"- **Message excerpt:** \"{f.get('message', '')}\"")
                lines.append("")
            if len(followups) > 3:
                lines.append(f"_...and {len(followups) - 3} more follow-up(s)._")
        else:
            lines.append("No follow-ups detected in this project's conversation.")
        return "\n".join(lines), True

    elif is_meetings:
        meetings = intel.get("meetings", {})
        tot = meetings.get("total_meetings", 0)
        m_list = meetings.get("meetings_list", [])
        lines = [f"#### Project Meetings Scheduled/Completed ({tot})", ""]
        if m_list:
            for idx, m in enumerate(m_list):
                lines.append(f"**{idx+1}. Meeting reference on {m.get('date', '')}**")
                lines.append(f"- **Sender:** {m.get('sender', 'System')}")
                lines.append(f"- **Message excerpt:** \"{m.get('message', '')}\"")
                lines.append("")
        else:
            lines.append("No meetings detected in this project's conversation.")
        return "\n".join(lines), True

    elif is_docs:
        links = intel.get("links", {})
        doc_count = links.get('documents', 0)
        lines = [
            "#### Shared Documents & Media",
            f"- **Shared Documents (PDF/Word/Excel):** {doc_count}",
            f"- **Google Drive links:** {links.get('gdrive', 0)}",
            f"- **Canva design links:** {links.get('canva', 0)}",
            f"- **Google Docs links:** {links.get('gdocs', 0)}",
            f"- **YouTube links:** {links.get('youtube', 0)}",
            f"- **Shared Images:** {links.get('images', 0)}",
            f"- **Shared Videos:** {links.get('videos', 0)}",
            f"- **WhatsApp Media Omitted entries:** {links.get('media_omitted', 0)}"
        ]
        if doc_count == 0:
            lines.append("\nNo documents detected in this project's conversation.")
        return "\n".join(lines), True

    elif is_msg_count:
        tot = intel.get("total_messages", 0)
        if not tot:
            return "No messages detected in this project's conversation.", True
        return f"A total of **{tot}** messages were exchanged in the analyzed period.", True

    elif is_duration:
        dates = intel.get("project_dates", {})
        first = dates.get("first_activity", "N/A")
        last = dates.get("last_activity", "N/A")
        days = dates.get("duration_days", 0)
        if not days:
            return "No project duration detected in this project's conversation.", True
        return f"#### Project Duration  \n- **First Activity:** {first}  \n- **Last Activity:** {last}  \n- **Total Duration:** {days} days", True

    return None, False


def ask_chitti_page():
    # Breadcrumbs (Part 8 & UI Cleanup)
    p_meta = st.session_state.get("active_report_meta")
    if p_meta is not None:
        proj_name = st.session_state.get('project_name') or 'Unnamed Project'
        version = p_meta.get("version", "1")
        st.markdown(
            f"<div style='color: gray; font-size: 0.9em; margin-bottom: 10px;'>"
            f"Reports &gt; {proj_name} &gt; Report v{version} &gt; Ask Chitti"
            f"</div>",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f"<div style='color: gray; font-size: 0.9em; margin-bottom: 10px;'>"
            f"Ask Chitti"
            f"</div>",
            unsafe_allow_html=True
        )
    
    col_t1, col_t2 = st.columns([4, 1])
    with col_t1:
        st.title("Ask Chitti")
        st.caption("Ask questions about your project.")
    with col_t2:
        if st.button("Back to Reports", key="ask_chitti_back_to_reports", use_container_width=True):
            st.switch_page("pages/Reports.py")
            
    # Project Context Card (Part 7 & Active Project Banner)
    if st.session_state.get("report_data"):
        meta = st.session_state.get("active_report_meta") or {}
        report_data = st.session_state.report_data
        
        num_completed = len(report_data.get("completed_tasks", []))
        num_pending = len(report_data.get("pending_tasks", []))
        num_requests = len(report_data.get("new_requests", []))
        num_messages = len(st.session_state.get("messages", []))
        
        try:
            from datetime import datetime
            gen_d = datetime.strptime(meta.get("generated_date", ""), "%Y-%m-%d").strftime("%d %b %Y")
        except Exception:
            gen_d = meta.get("generated_date", "")
            
        with st.container(border=True):
            st.markdown(f"#### Currently Working On: {st.session_state.get('project_name', 'Unnamed Project')}")
            cc1, cc2, cc3 = st.columns(3)
            with cc1:
                st.write(f"**Client:** {st.session_state.get('client_name', 'Unnamed Client')}")
                st.write(f"**Report:** Version {meta.get('version', '1')}")
            with cc2:
                st.write(f"**Reporting Period:** {meta.get('reporting_period', 'Not Specified')}")
                st.write(f"**Generated:** {gen_d}")
            with cc3:
                st.write(f"**Messages Analysed:** {num_messages}")
                st.write(f"**Completed Tasks:** {num_completed} | **Pending:** {num_pending} | **Requests:** {num_requests}")
    else:
        st.info("No active project selected.")

    # Project Intelligence Engine Summary (UI Cleanup & Part 6)
    intel_data = st.session_state.get("project_intelligence_engine")
    if intel_data is not None:
        pub = intel_data.get("published_posts", {})
        meetings = intel_data.get("meetings", {})
        dates = intel_data.get("project_dates", {})
        stats = intel_data.get("participant_stats", {})
        
        with st.container(border=True):
            st.markdown("##### Project Intelligence Summary")
            ic1, ic2, ic3 = st.columns(3)
            with ic1:
                st.write(f"**Messages Exchanged:** {intel_data.get('total_messages', 0)}")
                st.write(f"**Participants:** {len(intel_data.get('participants', []))}")
            with ic2:
                st.write(f"**Published Posts:** {pub.get('total_published', 0)}")
                st.write(f"**Approvals:** {len(intel_data.get('approvals', []))} | **Follow-ups:** {len(intel_data.get('followups', []))}")
            with ic3:
                st.write(f"**Meetings:** {meetings.get('total_meetings', 0)}")
                st.write(f"**Most Active Member:** {stats.get('most_active', 'N/A')}")
                
            first_act = dates.get("first_activity", "N/A")
            last_act = dates.get("last_activity", "N/A")
            st.caption(f"Project Duration: {first_act} → {last_act} ({dates.get('duration_days', 0)} days)")

    # Initialize input query in session state if not present
    if "input_q" not in st.session_state:
        st.session_state.input_q = ""

    # Initialize clear flag if not present
    if "clear_input_on_next_run" not in st.session_state:
        st.session_state.clear_input_on_next_run = False

    # Pre-instantiation state clearing pattern
    if st.session_state.clear_input_on_next_run:
        st.session_state.input_q = ""
        st.session_state.clear_input_on_next_run = False

    # Initialize search states
    if "search_query" not in st.session_state:
        st.session_state.search_query = ""
    if "search_sender_filter" not in st.session_state:
        st.session_state.search_sender_filter = "All Senders"

    # Robust report data validation
    report_data = st.session_state.get("report_data")
    has_report = isinstance(report_data, dict) and len(report_data) > 0

    # Warning banner above chat if report data is missing
    if not has_report:
        st.warning("Generate a report on the Dashboard to enable Ask Chitti.")

    # Initialize chat history in session state
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Callbacks for suggestions and clearing chat
    def set_question(q):
        st.session_state.input_q = q

    def clear_chat():
        st.session_state.chat_history = []
        st.session_state.input_q = ""

    def clear_search_callback():
        st.session_state.search_query = ""
        st.session_state.search_sender_filter = "All Senders"

    # Conversation Search Section
    st.subheader("Search Conversation")
    
    messages_list = st.session_state.get("messages", [])
    
    # Populate unique senders dynamically
    senders = sorted(list(set(m.get("sender", "System") for m in messages_list if m.get("sender"))))
    sender_options = ["All Senders"] + senders

    # Try to find if selected sender is still in options
    current_sender_filter = st.session_state.search_sender_filter
    if current_sender_filter not in sender_options:
        current_sender_filter = "All Senders"

    try:
        sender_index = sender_options.index(current_sender_filter)
    except ValueError:
        sender_index = 0

    # Layout search controls
    search_col1, search_col2, search_col3 = st.columns([6, 3, 1])
    
    with search_col1:
        st.text_input(
            "Search query",
            value=st.session_state.search_query,
            placeholder="Search messages, tasks, people or keywords...",
            key="search_query",
            label_visibility="collapsed"
        )
        
    with search_col2:
        st.selectbox(
            "Filter by Sender",
            options=sender_options,
            index=sender_index,
            key="search_sender_filter",
            label_visibility="collapsed"
        )
        
    with search_col3:
        st.button("Clear", use_container_width=True, key="clear_search_btn", on_click=clear_search_callback)

    # Search Results Rendering
    query_active = bool(st.session_state.search_query.strip())
    selected_sender = st.session_state.search_sender_filter
    sender_active = (selected_sender != "All Senders")
    
    if not messages_list:
        st.info("No conversation history available. Please upload a WhatsApp chat file on the Dashboard.")
    else:
        if query_active or sender_active:
            matched_indices = []
            for idx, msg in enumerate(messages_list):
                if sender_active and msg.get("sender", "System") != selected_sender:
                    continue
                if query_active and not matches_query_only(msg, st.session_state.search_query):
                    continue
                matched_indices.append(idx)
            
            st.write(f"**Found {len(matched_indices)} matching messages:**")
            
            if matched_indices:
                display_limit = 50
                for idx in matched_indices[:display_limit]:
                    msg = messages_list[idx]
                    sender = msg.get("sender", "System")
                    dt = msg.get("date")
                    body = msg.get("body", "")
                    time_str = dt.strftime("%I:%M %p") if dt else ""
                    date_str = dt.strftime("%d %b %Y") if dt else ""
                    
                    prev_msg = messages_list[idx - 1] if idx > 0 else None
                    next_msg = messages_list[idx + 1] if idx < len(messages_list) - 1 else None
                    
                    with st.container(border=True):
                        st.markdown(f"**{sender}** • {date_str} • {time_str}")
                        
                        if prev_msg:
                            p_sender = prev_msg.get("sender", "System")
                            p_body = prev_msg.get("body", "")
                            p_dt = prev_msg.get("date")
                            p_time = p_dt.strftime("%I:%M %p") if p_dt else ""
                            st.markdown(f"<span style='color: gray; font-size: 0.9em; padding-left: 15px; display: block;'>Previous message: <b>{p_sender}</b> ({p_time}): {p_body}</span>", unsafe_allow_html=True)
                            
                        st.markdown(f"<div style='border-left: 3px solid #ff4b4b; padding-left: 10px; margin: 5px 0; font-weight: 500;'>{body}</div>", unsafe_allow_html=True)
                        
                        if next_msg:
                            n_sender = next_msg.get("sender", "System")
                            n_body = next_msg.get("body", "")
                            n_dt = next_msg.get("date")
                            n_time = n_dt.strftime("%I:%M %p") if n_dt else ""
                            st.markdown(f"<span style='color: gray; font-size: 0.9em; padding-left: 15px; display: block;'>Next message: <b>{n_sender}</b> ({n_time}): {n_body}</span>", unsafe_allow_html=True)
                
                if len(matched_indices) > display_limit:
                    st.warning(f"Showing first {display_limit} of {len(matched_indices)} results. Please refine your search query.")
            else:
                st.info("No matching messages found for your search criteria.")
        else:
            st.info("Enter a query or select a sender above to search the conversation history.")

    st.divider()

    # Suggested Questions (Quick Actions) Grid
    st.write("**Suggested Questions:**")
    suggestions = [
        "How many LinkedIn posts were published?",
        "How many approvals were received?",
        "Who was the most active member?",
        "How many meetings took place?",
        "What is the average response time?",
        "How many Instagram posts were published?",
        "How many follow-ups were sent?",
        "What are the project participants?",
        "How many documents were shared?",
        "How long has this project been running?",
    ]

    cols = st.columns(2)
    for idx, sug in enumerate(suggestions):
        col = cols[idx % 2]
        col.button(
            sug,
            on_click=set_question,
            args=(sug,),
            use_container_width=True,
            key=f"sug_btn_{idx}"
        )

    st.divider()

    # Render Conversation History
    for chat in st.session_state.chat_history:
        with st.chat_message(chat["role"]):
            st.write(chat["content"])

    st.write("")

    # Chat Input Form and Action Buttons on a single row
    chat_col, clear_col = st.columns([7.5, 2.5])

    with chat_col:
        with st.form("chat_form", clear_on_submit=False):
            input_col, ask_col = st.columns([8, 2])
            with input_col:
                st.text_input(
                    "Ask a question about this project...",
                    placeholder="Ask anything about this project...",
                    key="input_q",
                    label_visibility="collapsed",
                )
            with ask_col:
                ask_clicked = st.form_submit_button(
                    "Ask", use_container_width=True, disabled=not has_report
                )

    with clear_col:
        st.button(
            "Clear Conversation",
            on_click=clear_chat,
            use_container_width=True,
            key="clear_chat_btn"
        )

    # Process user query
    if ask_clicked:
        if not has_report:
            st.warning("Please generate a report on the Dashboard first.")
        else:
            question = st.session_state.input_q
            if not question.strip():
                st.warning("Please enter a question.")
            else:
                # 1. Smart Routing: Check if Factual Question
                intel_data = st.session_state.get("project_intelligence_engine")
                answer_text, was_factual = route_and_answer_question(question, intel_data)
                
                if was_factual:
                    # Append user question and assistant answer to history
                    st.session_state.chat_history.append(
                        {"role": "user", "content": question}
                    )
                    st.session_state.chat_history.append(
                        {"role": "assistant", "content": answer_text}
                    )
                    st.session_state.clear_input_on_next_run = True
                    st.rerun()
                    
                # 2. Reasoning Questions fallback
                with st.spinner("Thinking..."):
                    try:
                        # Classify user question to build context dynamically (Dynamic Context Builder)
                        q_clean = question.lower().strip()
                        
                        is_completed = any(kw in q_clean for kw in ["completed", "done", "finished", "what work", "achieved", "complete"])
                        is_pending = any(kw in q_clean for kw in ["pending", "todo", "remaining", "left", "incomplete"])
                        is_evidence = any(kw in q_clean for kw in ["evidence", "quote", "supporting evidence", "supporting quotes"])
                        is_draft = any(kw in q_clean for kw in ["email", "draft", "weekly update", "mom", "meeting mom", "update"])
                        
                        # Check if asking about a specific date/day
                        day_messages, target_day = get_messages_for_day(question, messages_list)
                        
                        # Build custom compact context block
                        dynamic_context = ""
                        
                        if target_day is not None:
                            day_str = target_day.strftime("%d %b %Y")
                            if day_messages:
                                msg_lines = []
                                for m in day_messages:
                                    m_sender = m.get("sender", "System")
                                    m_dt = m.get("date")
                                    m_time = m_dt.strftime("%I:%M %p") if m_dt else "Unknown"
                                    msg_lines.append(f"[{day_str} {m_time}] {m_sender}: {m.get('body', '')}")
                                dynamic_context = f"\nWhatsApp Messages from {day_str}:\n" + "\n".join(msg_lines) + "\n"
                            else:
                                dynamic_context = f"\nNo WhatsApp messages found in logs for {day_str}.\n"
                                
                        elif is_completed:
                            comp_tasks = report_data.get("completed_tasks", [])
                            comp_lines = []
                            for idx, t in enumerate(comp_tasks):
                                if isinstance(t, dict):
                                    comp_lines.append(f"- Task {idx+1}: {t.get('task', 'Unnamed')}\n  Reasoning: {t.get('reason', '')}\n  Time Spent: {t.get('estimated_hours', 0.0)} hours")
                            comp_tasks_str = "\n".join(comp_lines)
                            dynamic_context = f"""
Project Summary:
{report_data.get("project_summary", "")}

Completed Tasks:
{comp_tasks_str}
"""
                            
                        elif is_pending:
                            pend_tasks = report_data.get("pending_tasks", [])
                            pend_lines = [f"- {t}" for t in pend_tasks]
                            pend_tasks_str = "\n".join(pend_lines)
                            dynamic_context = f"""
Pending Tasks:
{pend_tasks_str}
"""
                            
                        elif is_evidence:
                            retrieved_context, max_score = retrieve_relevant_messages(question, messages_list)
                            dynamic_context = f"""
Relevant Conversation Evidence Snippets:
{retrieved_context if retrieved_context else "No relevant messages found."}
"""
                            
                        elif is_draft:
                            comp_tasks = report_data.get("completed_tasks", [])
                            comp_lines = [f"- {t.get('task', 'Unnamed')} (Time Spent: {t.get('estimated_hours', 0.0)} hrs)" for t in comp_tasks if isinstance(t, dict)]
                            comp_tasks_str = "\n".join(comp_lines)
                            
                            pend_tasks = report_data.get("pending_tasks", [])
                            pend_lines = [f"- {t}" for t in pend_tasks]
                            pend_tasks_str = "\n".join(pend_lines)
                            
                            retrieved_context, max_score = retrieve_relevant_messages(question, messages_list)
                            
                            dynamic_context = f"""
Project Summary:
{report_data.get("project_summary", "")}

Completed Tasks:
{comp_tasks_str}

Pending Tasks:
{pend_tasks_str}

Relevant Conversation Evidence Snippets:
{retrieved_context if retrieved_context else "No relevant messages found."}
"""
                            
                        else:
                            retrieved_context, max_score = retrieve_relevant_messages(question, messages_list)
                            dynamic_context = f"""
Project Summary:
{report_data.get("project_summary", "")}

Client Report Summary:
{report_data.get("client_report", "")}

Relevant Conversation Snippets (Evidence):
{retrieved_context if retrieved_context else "No relevant messages found."}
"""

                        latest_conv_date = st.session_state.report_data.get("latest_conversation_date", "Not Available")
                        today_date = datetime.date.today()
                        
                        outdated_warning_instruction = ""
                        try:
                            conv_date_parsed = datetime.datetime.strptime(latest_conv_date, "%d %b %Y").date()
                            if conv_date_parsed < today_date:
                                outdated_warning_instruction = f"""
IMPORTANT Freshness Disclaimer Notice:
This report is based on conversations available until {latest_conv_date}. Today's date is {today_date.strftime('%d %b %Y')}.
Because the report is based on outdated conversations, you MUST start your response exactly with the following notice:
"This report is based on conversations available until {latest_conv_date}. Recent work performed after this date may not be included."
Do not paraphrase this notice. Print it exactly as the very first sentence of your response.
"""
                        except Exception:
                            pass

                        # Build project intelligence context (Part 8)
                        intel_context = ""
                        intel = st.session_state.get("project_intelligence_engine")
                        if intel:
                            pub = intel.get("published_posts", {})
                            dates = intel.get("project_dates", {})
                            stats = intel.get("participant_stats", {})
                            intel_context = f"""
Deterministic Project Intelligence Metrics:
- Total Messages Exchanged: {intel.get('total_messages', 0)}
- Participants: {', '.join(intel.get('participants', []))}
- Project Duration: {dates.get('first_activity', 'N/A')} to {dates.get('last_activity', 'N/A')} ({dates.get('duration_days', 0)} days)
- Most Active Member: {stats.get('most_active', 'N/A')}
- Published Posts Total: {pub.get('total_published', 0)}
- Approvals Count: {len(intel.get('approvals', []))}
- Follow-ups Count: {len(intel.get('followups', []))}
- Meetings Count: {intel.get('meetings', {}).get('total_meetings', 0)}
"""

                        # Construct system prompt context with dynamic_context instead of full report_data payload
                        system_prompt = f"""You are Chitti, an AI Project Intelligence Assistant.

Your goal is to answer the user's questions about the project.

{outdated_warning_instruction}

Project Details:
- Project Name: {st.session_state.get("project_name", "Not Specified")}
- Client: {st.session_state.get("client_name", "Not Specified")}

{intel_context}

Current Question: {question}

Context Information:
{dynamic_context}

FALLBACK HANDLING AND HALLUCINATION PREVENTION:
If the user's question requires specific information from the WhatsApp conversation (such as who made a request, when a meeting or task occurred, specific links, dates, or chat messages) AND that information is not present in the provided 'Context Information' (or if there is insufficient evidence to answer), you MUST respond with exactly:
"I couldn't find enough evidence in the uploaded conversations."
Never fabricate or invent names, dates, links, or details. Do not refer to details that are not provided in the Context Information.

MANDATORY EVIDENCE CITATION:
If you use any conversation messages from the context as evidence, at the end of your response, you MUST create a dedicated section titled "### Evidence Used" listing the precise messages you used as evidence.
Each citation in the Evidence Used section must include:
1. Date (e.g. 22 Jun 2026)
2. Sender Name
3. The exact message quote (surrounded by double quotes)
4. A confidence level for the citation (High, Medium, or Low).

Format the Evidence Used section exactly like this:
### Evidence Used
- **Date:** [Date]
  **Sender:** [Sender Name]
  **Message:** "[Exact Message Quote]"
  **Confidence:** [High/Medium/Low]

If multiple conversations support the answer, you MUST display them in chronological order of their timestamps.

Please use clean Markdown with headings and bullet points for your answer. Do not include emojis in your response.
"""
                        # Build messages including history (restricted to maximum 5 exchanges / last 10 messages)
                        messages = [{"role": "system", "content": system_prompt}]
                        for chat in st.session_state.chat_history[-10:]:
                            messages.append(
                                {"role": chat["role"], "content": chat["content"]}
                            )
                        messages.append({"role": "user", "content": question})

                        # Call OpenRouter API
                        response = client.chat.completions.create(
                            model=MODEL_NAME,
                            messages=messages,
                            temperature=0,
                            max_tokens=800
                        )
                        answer = response.choices[0].message.content

                        # Append user question and assistant answer to history
                        st.session_state.chat_history.append(
                            {"role": "user", "content": question}
                        )
                        st.session_state.chat_history.append(
                            {"role": "assistant", "content": answer}
                        )

                        # Set clear flag to reset input_q on next run
                        st.session_state.clear_input_on_next_run = True
                        st.rerun()

                    except Exception as e:
                        st.error(f"Error communicating with AI: {str(e)}")


ask_chitti_page()