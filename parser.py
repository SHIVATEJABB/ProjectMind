import re
from datetime import datetime
import streamlit as st


def read_text_file(uploaded_file):
    if uploaded_file is None:
        return ""

    return uploaded_file.read().decode("utf-8")


def is_meaningful_message(text):
    """
    Returns True if the message content seems to have meaningful project evidence,
    and False if it is a greeting, thank you message, simple reply, emoji-only,
    or trivial scheduling phrase.
    """
    cleaned = text.strip().lower()
    
    # 1. Skip if message has no letters or digits (e.g. emoji-only or symbols)
    if not any(char.isalnum() for char in cleaned):
        return False
        
    # 2. Skip simple greetings
    greetings = {
        "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
        "hi all", "hello all", "hi team", "hello team", "hey team", "hi guys", "hello guys"
    }
    if cleaned in greetings:
        return False
        
    # 3. Skip thank yous / simple acknowledgements
    thank_yous = {
        "thanks", "thank you", "thanks!", "thank you!", "thanks all", "thanks team",
        "great thanks", "many thanks", "ok", "okay", "done", "done.", "k", "ok.",
        "sure", "sure.", "cool", "yes", "no", "yeah", "yup", "nope", "noted", "noted.",
        "noted, thanks", "noted thanks", "got it", "got it.", "will do", "will do."
    }
    if cleaned in thank_yous:
        return False
        
    # 4. Skip trivial scheduling phrases
    scheduling_phrases = {
        "joining now", "joined", "can we connect?", "let's connect", "are you free?", 
        "ping me when free", "ping me when done", "call you in 5", "call you in 10", 
        "on my way", "ready", "ready?", "ready.", "start the call", "join the call",
        "please join", "please join now", "zoom link?", "gmeet link?", "teams link?",
        "here is the link"
    }
    if cleaned in scheduling_phrases:
        return False
        
    return True


def parse_whatsapp_datetime(date_str, time_str):
    import datetime as dt_module
    import re
    # 1. Parse time
    time_str = re.sub(r'\s+', ' ', time_str.strip().upper())
    has_ampm = "AM" in time_str or "PM" in time_str
    
    time_formats = []
    if has_ampm:
        time_formats = ["%I:%M:%S %p", "%I:%M %p", "%H:%M:%S %p", "%H:%M %p"]
    else:
        time_formats = ["%H:%M:%S", "%H:%M"]
        
    time_obj = None
    for tf in time_formats:
        try:
            time_obj = dt_module.datetime.strptime(time_str, tf).time()
            break
        except ValueError:
            pass
            
    if not time_obj:
        return None
        
    # 2. Parse date
    sep_match = re.search(r'[/\.-]', date_str)
    if not sep_match:
        return None
    sep = sep_match.group(0)
    parts = date_str.split(sep)
    if len(parts) != 3:
        return None
        
    p0, p1, p2 = parts
    if len(p0) == 4:
        date_formats = [f"%Y{sep}%m{sep}%d", f"%Y{sep}%d{sep}%m"]
    else:
        year_fmt = "%Y" if len(p2) == 4 else "%y"
        date_formats = [
            f"%d{sep}%m{sep}{year_fmt}",
            f"%m{sep}%d{sep}{year_fmt}",
            f"%y{sep}%m{sep}%d"
        ]
        
    date_obj = None
    for df in date_formats:
        try:
            date_obj = dt_module.datetime.strptime(date_str, df).date()
            break
        except ValueError:
            pass
            
    if not date_obj:
        return None
        
    return dt_module.datetime.combine(date_obj, time_obj)


@st.cache_data
def extract_messages(chat_text):
    """
    Extracts WhatsApp messages by dynamically detecting different export header formats
    (such as iOS bracketed and Android/unbracketed style) and parsing varying formats.
    """
    import re
    
    # Format 1 (iOS style): [22/08/25, 12:58:57 PM] Name: Message
    pattern_ios = re.compile(r"^\[(\d{1,4}[/\.-]\d{1,2}[/\.-]\d{1,4}),\s*(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[APap][Mm])?)\]", re.MULTILINE)
    
    # Format 2 (Android style): 26/11/2025, 12:38 - Name: Message
    pattern_android = re.compile(r"^(\d{1,4}[/\.-]\d{1,2}[/\.-]\d{1,4}),\s*(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[APap][Mm])?)\s*-\s*", re.MULTILINE)
    
    matches = list(pattern_ios.finditer(chat_text))
    if len(matches) < 2:
        matches = list(pattern_android.finditer(chat_text))
        
    if not matches:
        return []
        
    messages = []
    seen_bodies = set()
    
    for i, match in enumerate(matches):
        start = match.start()
        end = (
            matches[i + 1].start()
            if i + 1 < len(matches)
            else len(chat_text)
        )
        block = chat_text[start:end].strip()
        
        date_str = match.group(1)
        time_str = match.group(2)
        
        dt = parse_whatsapp_datetime(date_str, time_str)
        if dt is None:
            continue
            
        header_len = match.end() - match.start()
        after_header = block[header_len:].strip()
        
        colon_idx = after_header.find(":")
        if colon_idx != -1:
            msg_sender = after_header[:colon_idx].strip()
            msg_body = after_header[colon_idx + 1:].strip()
        else:
            msg_sender = "System"
            msg_body = after_header
            
        # Filter out meaningless messages
        if not is_meaningful_message(msg_body):
            continue
            
        # Deduplicate identical message bodies
        body_lower = msg_body.lower()
        if body_lower in seen_bodies:
            continue
        seen_bodies.add(body_lower)
        
        msg_id = f"MSG_{len(messages) + 1:04d}"
        messages.append({
            "id": msg_id,
            "date": dt,
            "text": block,
            "sender": msg_sender,
            "body": msg_body
        })
        
    return messages


def conversation_summary(messages):
    if len(messages) == 0:
        return {
            "count": 0,
            "first": None,
            "last": None
        }

    return {
        "count": len(messages),
        "first": messages[0]["date"],
        "last": messages[-1]["date"]
    }


def check_coverage(messages, start_date, end_date):
    summary = conversation_summary(messages)

    if summary["count"] == 0:
        return {
            "status": "NO_DATA"
        }

    first = summary["first"].date()
    last = summary["last"].date()

    if end_date < first or start_date > last:
        return {
            "status": "NO_DATA",
            "available_start": first,
            "available_end": last
        }

    if start_date < first or end_date > last:
        return {
            "status": "PARTIAL",
            "available_start": first,
            "available_end": last
        }

    return {
        "status": "AVAILABLE",
        "available_start": first,
        "available_end": last
    }


def filter_messages_by_date(messages, start_date, end_date):
    filtered = []
    for message in messages:
        if start_date <= message["date"].date() <= end_date:
            filtered.append(message)
    return filtered


def combine_documents(filtered_messages, supporting_text=""):
    import re
    # Limit number of messages and cap individual message size to prevent oversized prompts
    cleaned_messages = []
    seen_bodies = set()
    for msg in filtered_messages:
        body = msg.get("body", "")
        # Remove repeated/duplicate messages normalized by whitespace
        body_normalized = re.sub(r'\s+', ' ', body.lower().strip())
        if not body_normalized or body_normalized in seen_bodies:
            continue
        seen_bodies.add(body_normalized)
        
        # Cap individual message body to 200 characters to keep it concise
        if len(body) > 200:
            msg_text = msg["text"]
            bracket_idx = msg_text.find("]")
            header = msg_text[:bracket_idx + 1] if bracket_idx != -1 else ""
            sender = msg.get("sender", "System")
            msg_text = f"{header} {sender}: {body[:200]}... [truncated]"
        else:
            msg_text = msg["text"]
            
        # Prefix with message ID for easy AI reference
        msg_id = msg.get("id", "MSG_0000")
        msg_text = f"[{msg_id}] {msg_text}"
        cleaned_messages.append(msg_text)

    # If conversation is massive, keep the 150 most descriptive messages in chronological order
    if len(cleaned_messages) > 150:
        indexed_msgs = list(enumerate(cleaned_messages))
        # Sort by message length descending to keep descriptive ones
        indexed_msgs.sort(key=lambda x: len(x[1]), reverse=True)
        keep_indices = set(idx for idx, _ in indexed_msgs[:150])
        # Reconstruct list maintaining chronological order
        cleaned_messages = [msg for idx, msg in enumerate(cleaned_messages) if idx in keep_indices]

    conversation = "\n\n".join(cleaned_messages)
    
    # Cap supporting text to prevent huge prompts
    if len(supporting_text) > 8000:
        supporting_text = supporting_text[:8000] + "\n... [supporting document truncated due to length]"

    return f"""
=========================
WHATSAPP CONVERSATION
=========================

{conversation}

=========================
SUPPORTING DOCUMENT
=========================

{supporting_text}
"""