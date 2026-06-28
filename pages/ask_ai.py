import streamlit as st
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


def ask_ai_page():
    st.title("Ask Chitti")
    st.caption("Ask questions about your project.")

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
        "Explain this report",
        "What work was completed?",
        "What is pending?",
        "Show supporting evidence",
        "Draft client email",
        "Draft weekly update",
        "Draft meeting MOM",
        "Generate executive summary",
        "Identify project risks",
        "Recommend next steps",
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

                        # Construct system prompt context with dynamic_context instead of full report_data payload
                        system_prompt = f"""You are Chitti, an AI Project Intelligence Assistant.

Your goal is to answer the user's questions about the project.

{outdated_warning_instruction}

Project Details:
- Project Name: {st.session_state.get("project_name", "Not Specified")}
- Client: {st.session_state.get("client_name", "Not Specified")}

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
                            max_tokens=1000
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


ask_ai_page()