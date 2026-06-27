import re
import datetime

def compute_project_intelligence(messages):
    """
    Computes deterministic metrics and statistics from parsed WhatsApp messages.
    Does NOT use AI.
    """
    if not messages:
        return {
            "total_messages": 0,
            "participants": [],
            "participant_stats": {
                "messages_per_participant": {},
                "most_active": "N/A",
                "least_active": "N/A"
            },
            "links": {
                "instagram": 0,
                "linkedin": 0,
                "facebook": 0,
                "twitter": 0,
                "youtube": 0,
                "gdrive": 0,
                "canva": 0,
                "gdocs": 0,
                "media_omitted": 0,
                "documents": 0,
                "images": 0,
                "videos": 0
            },
            "published_posts": {
                "instagram": [],
                "linkedin": [],
                "facebook": [],
                "twitter": [],
                "total_published": 0
            },
            "approvals": [],
            "followups": [],
            "meetings": {
                "total_meetings": 0,
                "meeting_dates": [],
                "meetings_list": []
            },
            "activity": {},
            "project_dates": {
                "first_activity": "N/A",
                "last_activity": "N/A",
                "duration_days": 0
            }
        }

    total_messages = len(messages)
    
    # Track participants and message counts
    messages_per_participant = {}
    for msg in messages:
        sender = msg.get("sender") or "System"
        messages_per_participant[sender] = messages_per_participant.get(sender, 0) + 1
        
    participants = list(messages_per_participant.keys())
    
    # Sort participants by message activity
    sorted_participants = sorted(messages_per_participant.items(), key=lambda x: x[1], reverse=True)
    most_active = sorted_participants[0][0] if sorted_participants else "N/A"
    least_active = sorted_participants[-1][0] if sorted_participants else "N/A"

    # Sort messages chronologically to calculate first/last activity
    valid_msgs = []
    for msg in messages:
        dt = msg.get("date")
        if isinstance(dt, str):
            try:
                dt = datetime.datetime.fromisoformat(dt)
            except Exception:
                pass
        if isinstance(dt, (datetime.datetime, datetime.date)):
            valid_msgs.append((dt, msg))
            
    valid_msgs.sort(key=lambda x: x[0])
    
    first_activity = "N/A"
    last_activity = "N/A"
    duration_days = 0
    if valid_msgs:
        first_dt = valid_msgs[0][0]
        last_dt = valid_msgs[-1][0]
        first_activity = first_dt.strftime("%Y-%m-%d")
        last_activity = last_dt.strftime("%Y-%m-%d")
        f_date = first_dt.date() if isinstance(first_dt, datetime.datetime) else first_dt
        l_date = last_dt.date() if isinstance(last_dt, datetime.datetime) else last_dt
        duration_days = (l_date - f_date).days

    # Link/media counting regexes
    url_pattern = re.compile(r'https?://[^\s]+', re.IGNORECASE)
    
    instagram_links = 0
    linkedin_links = 0
    facebook_links = 0
    twitter_links = 0
    youtube_links = 0
    gdrive_links = 0
    canva_links = 0
    gdocs_links = 0
    
    instagram_urls = []
    linkedin_urls = []
    facebook_urls = []
    twitter_urls = []
    
    media_omitted = 0
    documents_count = 0
    images_count = 0
    videos_count = 0
    
    media_omitted_pattern = re.compile(r'<media\s+omitted>', re.IGNORECASE)
    image_pattern = re.compile(r'\b(image|photo|pic|jpeg|jpg|png)\b', re.IGNORECASE)
    video_pattern = re.compile(r'\b(video|mp4|mov|avi)\b', re.IGNORECASE)
    document_pattern = re.compile(r'\b(pdf|docx|xlsx|csv|pptx|zip|doc|xls|ppt|epub|txt)\b', re.IGNORECASE)
    
    # Approvals, followups, meetings
    approvals = []
    followups = []
    meetings_list = []
    meeting_dates = []
    
    # Phrases
    approval_phrases = ["looks good", "approved", "perfect", "go ahead", "proceed", "fine", "good to go", "done"]
    followup_phrases = ["following up", "reminder", "any updates", "checking in", "gentle reminder", "please update", "waiting for"]
    meeting_keywords = ["meeting scheduled", "meeting completed", "google meet", "zoom", "teams", "meet.google.com", "zoom.us", "teams.microsoft.com", "calendar"]

    # Activity timeline (messages per day)
    activity = {}

    for dt, msg in valid_msgs:
        body = msg.get("body", "")
        body_lower = body.lower()
        sender = msg.get("sender", "System")
        date_str = dt.strftime("%d %b")
        
        # Timeline
        activity[date_str] = activity.get(date_str, 0) + 1
        
        # Link checks
        urls = url_pattern.findall(body)
        for url in urls:
            url = url.rstrip('.,;:?!")}]')
            url_lower = url.lower()
            if "instagram.com" in url_lower:
                instagram_links += 1
                instagram_urls.append(url)
            elif "linkedin.com" in url_lower:
                linkedin_links += 1
                linkedin_urls.append(url)
            elif "facebook.com" in url_lower:
                facebook_links += 1
                facebook_urls.append(url)
            elif "twitter.com" in url_lower or "x.com" in url_lower:
                twitter_links += 1
                twitter_urls.append(url)
            elif "youtube.com" in url_lower or "youtu.be" in url_lower:
                youtube_links += 1
            elif "drive.google.com" in url_lower:
                gdrive_links += 1
            elif "canva.com" in url_lower:
                canva_links += 1
            elif "docs.google.com" in url_lower:
                gdocs_links += 1

        # Media/Attachment detection
        if media_omitted_pattern.search(body_lower):
            media_omitted += 1
        else:
            has_doc = False
            has_img = False
            has_vid = False
            
            if document_pattern.search(body_lower):
                documents_count += 1
                has_doc = True
            if image_pattern.search(body_lower):
                images_count += 1
                has_img = True
            if video_pattern.search(body_lower):
                videos_count += 1
                has_vid = True
                
            if not (has_doc or has_img or has_vid):
                if ".pdf" in body_lower or ".docx" in body_lower or ".xlsx" in body_lower:
                    documents_count += 1
                elif ".png" in body_lower or ".jpg" in body_lower or ".jpeg" in body_lower:
                    images_count += 1
                elif ".mp4" in body_lower or ".mov" in body_lower:
                    videos_count += 1

        # Approval Detection
        is_approved = False
        for phrase in approval_phrases:
            pattern = re.compile(rf'\b{re.escape(phrase)}\b', re.IGNORECASE)
            if pattern.search(body_lower):
                is_approved = True
                break
        if is_approved:
            approvals.append({
                "date": dt.strftime("%Y-%m-%d"),
                "sender": sender,
                "message": body
            })
            
        # Follow-up Detection
        is_followup = False
        for phrase in followup_phrases:
            pattern = re.compile(rf'\b{re.escape(phrase)}\b', re.IGNORECASE)
            if pattern.search(body_lower):
                is_followup = True
                break
        if is_followup:
            followups.append({
                "date": dt.strftime("%Y-%m-%d"),
                "sender": sender,
                "message": body
            })

        # Meeting Detection
        is_meeting = False
        for kw in meeting_keywords:
            if kw in body_lower:
                is_meeting = True
                break
        if is_meeting:
            meetings_list.append({
                "date": dt.strftime("%Y-%m-%d"),
                "sender": sender,
                "message": body
            })
            m_date_str = dt.strftime("%Y-%m-%d")
            if m_date_str not in meeting_dates:
                meeting_dates.append(m_date_str)

    total_published = len(instagram_urls) + len(linkedin_urls) + len(facebook_urls) + len(twitter_urls)

    # --- Average Response Time ---
    avg_response_minutes = 0.0
    if len(valid_msgs) >= 2:
        response_gaps = []
        for i in range(1, len(valid_msgs)):
            prev_dt, prev_msg = valid_msgs[i - 1]
            curr_dt, curr_msg = valid_msgs[i]
            prev_sender = prev_msg.get("sender", "")
            curr_sender = curr_msg.get("sender", "")
            if prev_sender and curr_sender and prev_sender != curr_sender:
                gap_minutes = (curr_dt - prev_dt).total_seconds() / 60.0
                if 0 < gap_minutes < 10080:  # ignore gaps > 1 week
                    response_gaps.append(gap_minutes)
        if response_gaps:
            avg_response_minutes = round(sum(response_gaps) / len(response_gaps), 1)

    # --- Activity Feed ---
    priority_keywords = [
        "approved", "shared", "completed", "published", "meeting", "zoom",
        "google meet", "following up", "reminder", "update"
    ]
    url_re = re.compile(r'https?://[^\s]+', re.IGNORECASE)

    feed_events = []
    for dt, msg in valid_msgs:
        body = msg.get("body", "")
        body_lower = body.lower()
        sender = msg.get("sender", "System")
        date_key = dt.strftime("%Y-%m-%d")

        is_approval = any(p in body_lower for p in ["approved", "looks good", "perfect", "go ahead", "good to go"])
        is_followup = any(p in body_lower for p in ["following up", "reminder", "gentle reminder", "any updates", "checking in"])
        is_meeting = any(k in body_lower for k in meeting_keywords)
        has_url = bool(url_re.search(body))
        has_priority_kw = any(kw in body_lower for kw in priority_keywords)
        is_long_msg = len(body.strip()) > 30

        should_include = is_approval or is_followup or is_meeting or has_url or (has_priority_kw and is_long_msg)

        if should_include:
            summary_text = body.strip()[:120]
            feed_events.append({
                "date": date_key,
                "sender": sender,
                "summary": summary_text,
                "_dt": dt
            })

    # Sort newest-first, take up to 15
    feed_events.sort(key=lambda e: e["_dt"], reverse=True)
    activity_feed = []
    for ev in feed_events[:15]:
        activity_feed.append({
            "date": ev["date"],
            "sender": ev["sender"],
            "summary": ev["summary"]
        })

    return {
        "total_messages": total_messages,
        "participants": participants,
        "participant_stats": {
            "messages_per_participant": messages_per_participant,
            "most_active": most_active,
            "least_active": least_active
        },
        "links": {
            "instagram": instagram_links,
            "linkedin": linkedin_links,
            "facebook": facebook_links,
            "twitter": twitter_links,
            "youtube": youtube_links,
            "gdrive": gdrive_links,
            "canva": canva_links,
            "gdocs": gdocs_links,
            "media_omitted": media_omitted,
            "documents": documents_count,
            "images": images_count,
            "videos": videos_count
        },
        "published_posts": {
            "instagram": instagram_urls,
            "linkedin": linkedin_urls,
            "facebook": facebook_urls,
            "twitter": twitter_urls,
            "total_published": total_published
        },
        "approvals": approvals,
        "followups": followups,
        "meetings": {
            "total_meetings": len(meetings_list),
            "meeting_dates": meeting_dates,
            "meetings_list": meetings_list
        },
        "activity": activity,
        "project_dates": {
            "first_activity": first_activity,
            "last_activity": last_activity,
            "duration_days": duration_days
        },
        "average_response_time_minutes": avg_response_minutes,
        "activity_feed": activity_feed
    }
