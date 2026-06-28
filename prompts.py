def format_previous_report(previous_data):
    if not previous_data or not isinstance(previous_data, dict):
        return ""
    
    summary = previous_data.get("project_summary", "No previous summary.")
    
    comp_tasks_str = ""
    comp_tasks = previous_data.get("completed_tasks", [])
    if isinstance(comp_tasks, list):
        for t in comp_tasks:
            if isinstance(t, dict):
                task_name = t.get("task", "Unknown Task")
                desc = t.get("reason", "")
                hours = t.get("estimated_hours", 0.0)
                comp_tasks_str += f"- Task: {task_name}\n  Details/Reasoning: {desc}\n  Time Spent: {hours} hours\n"
    
    pend_tasks_str = ""
    pend_tasks = previous_data.get("pending_tasks", [])
    if isinstance(pend_tasks, list):
        for t in pend_tasks:
            pend_tasks_str += f"- {t}\n"
            
    new_reqs_str = ""
    new_reqs = previous_data.get("new_requests", [])
    if isinstance(new_reqs, list):
        for r in new_reqs:
            new_reqs_str += f"- {r}\n"
            
    return f"""
----------------------------

PREVIOUS REPORT STATE (from the last reporting period)
You must use this to maintain task continuity:

Previous Project Summary:
{summary}

Previous Deliverables / Completed Tasks:
{comp_tasks_str or "None"}

Previous Pending Tasks:
{pend_tasks_str or "None"}

Previous Client Requests:
{new_reqs_str or "None"}
"""


def build_project_prompt(
    project_name,
    client_name,
    start_date,
    end_date,
    project_evidence,
    previous_report_data=None
):
    import json
    # Package parameters as a serialized JSON string so analyze_project can deserialize it
    data = {
        "project_name": project_name,
        "client_name": client_name,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "project_evidence": project_evidence,
        "previous_report_data": previous_report_data
    }
    return json.dumps(data)


def build_reconstruction_prompt(
    project_name,
    client_name,
    start_date,
    end_date,
    evidence,
    previous_report_data=None
):
    prev_str = format_previous_report(previous_report_data) if previous_report_data else ""
    
    return f"""You are a precise data extraction and project state reconstruction engine. 
Analyze the project evidence (conversations and supporting documents) and the previous report state to reconstruct the raw project state for {project_name} ({client_name}) during the period {start_date} to {end_date}.

PROJECT EVIDENCE:
{evidence}

{prev_str}

Extract the raw project state as a JSON object matching this schema:
{{
  "completed_activities": [
    {{
      "activity": "Brief, outcome-focused description of the completed action.",
      "estimated_hours": 2.0,
      "msg_ids": ["MSG_0001"]
    }}
  ],
  "pending_activities": [
    "Unresolved tasks or ongoing work items."
  ],
  "client_requests": [
    "New requests or instructions raised by the client."
  ],
  "client_decisions": [
    "Approvals, agreements, or choices made by the client."
  ],
  "risks": [
    "Risks, blockers, or issues mentioned."
  ]
}}

Guidelines:
- Identify all completed tasks from the evidence. Match each completed activity to exactly 1 or 2 relevant message IDs from the evidence.
- Identify pending work, client requests, client decisions/approvals, and risks.
- TASK CONTINUITY: If a previous report state is provided, check if the completed activities from the evidence are extensions of previous completed/pending tasks. If so, preserve the task names, cumulative hours, and evidence mapping.
- Return ONLY valid JSON. No comments, no backticks, no wrapping.
"""


def build_writer_prompt(
    project_name,
    client_name,
    start_date,
    end_date,
    project_state
):
    import json
    return f"""You are a senior project manager and consultant writing a professional monthly work completion report.
Format the provided project state into a client-ready document.

Project Name: {project_name}
Client Name: {client_name}
Reporting Period: {start_date} to {end_date}

PROJECT STATE:
{json.dumps(project_state, indent=2)}

Format the final response as a JSON object matching exactly this schema:
{{
    "project_summary": "High-level summary (max 80 words) of the progress made during this period.",
    "completed_tasks": [
        {{
            "task": "Dynamic workstream title grouping related activities (e.g. Website Optimisation).",
            "estimated_hours": 0.0,
            "confidence": 95,
            "confidence_reason": [
                "Task discussed across messages",
                "Evidence matched from logs"
            ],
            "verification_status": "Awaiting Supporting Documents",
            "reason": "Brief summary (max 40 words) describing the combined work stream.",
            "evidence_ids": ["MSG_0001"]
        }}
    ],
    "pending_tasks": [
        "Description of unresolved or ongoing tasks."
    ],
    "new_requests": [
        "Description of new client requests."
    ],
    "client_report": "A complete, professional client-ready report in markdown. Read instructions below.",
    "project_intelligence": {{
        "project_health": {{
            "status": "On Track",
            "explanation": "Brief status explanation."
        }},
        "insights": [
            {{
                "insight": "Insight statement.",
                "why": ["MSG_0001"]
            }}
        ],
        "potential_risks": [
            {{
                "risk": "Risk description.",
                "why": ["MSG_0002"]
            }}
        ],
        "recommended_next_steps": [
            "Action recommendation"
        ]
    }}
}}

Instructions for client_report formatting:
- Use the title: # Project Progress Report
- Include these sections in order:
  ## Reporting Period: {start_date} to {end_date}
  
  ## Overall Progress
  [Insert concise progress summary]
  
  ## Completed During This Period
  Group the completed activities from the project state into logical workstreams. For each workstream, create a dynamic title (e.g. Website Optimisation) and write concise outcome-focused bullets. Use maximum two bullet nesting levels. Do not create empty sections.
  
  ## Client Decisions
  List client decisions if present in project state. If none, do not include this section.
  
  ## Pending Work
  List pending activities if present. If none, do not include.
  
  ## Upcoming Work
  List upcoming tasks/new requests if present. If none, do not include.

Style guidelines:
- Outcome-focused bullets
- Professional business English, concise and filler-free.
- Banned words: Do NOT mention "WhatsApp" or "AI". Do not use "leveraging", "it is worth noting", "it should be noted", "comprehensive", "robust", "seamless", "cutting-edge", "transformative".
- No emojis.
- Return ONLY valid JSON. No comments, no backticks, no wrapping.
"""
