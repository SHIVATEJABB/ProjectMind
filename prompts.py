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
    prev_str = format_previous_report(previous_report_data) if previous_report_data else ""
    
    continuity_instruction = ""
    if previous_report_data:
        continuity_instruction = """
11. TASK CONTINUITY:
   * You must recognize task continuity. Do NOT duplicate tasks or delete existing tasks that have ongoing work.
   * Compare the new PROJECT EVIDENCE with the PREVIOUS REPORT STATE.
   * If a task from the previous report is still in progress or has additional work logged in the new project evidence, extend the task details (update its description/reasoning/evidence in "reason" and "evidence") rather than removing it or creating a new duplicate task.
   * Update the task's "estimated_hours" by adding the new effort spent during this period to the previous cumulative hours.
   * Ensure that ongoing tasks retain their continuity and any new progress is logged under the same task name where possible.
   * If a previous task is completed and has no new work, keep it in the list (or move it to completed state description) to preserve the historical record of deliverables.
"""

    return f"""
You are ProjectMind.

You analyze project evidence to reconstruct project work and produce professional, client-ready work completion reports.

Project Name:
{project_name}

Client:
{client_name}

Reporting Period:
{start_date} to {end_date}

----------------------------

PROJECT EVIDENCE

{project_evidence}
{prev_str}
----------------------------

Please read and analyze the project evidence carefully, following these instructions:

1. WORK COMPLETION REPORT FORMAT: The final "client_report" must be a professional work completion report suitable for sending directly to a paying client. It must read like a formal monthly consulting report prepared by a senior Project Manager or Consultant, NOT an AI summary or conversation log. The report must consist of EXACTLY these 7 sections in order, formatted with standard markdown headings:

   ### 1. Executive Summary
   A concise professional overview of the period. State overall progress, key achievements, and current status. Maximum 80 words.

   ### 2. Completed Work & Deliverables
   Group completed work into logical deliverables. For each deliverable include title, description, business outcome, and supporting activities. Expand using professional consulting language.

   ### 3. Client Decisions Received
   List explicit decisions or approvals made by the client during this period. If none, write: "No formal client decisions were recorded during this period."

   ### 4. Risks & Blockers
   Evidence-based risks only. If none, write: "No significant risks or blockers identified during this period."

   ### 5. Upcoming Activities
   List next planned activities and pending work items in priority order.

   ### 6. Recommendations
   Evidence-backed, practical next steps for the client and team.

   ### 7. Closing Summary
   One professional closing paragraph summarizing the period's progress and expressing forward momentum.

2. TREAT CHAT AS EVIDENCE: Treat the conversation records strictly as source evidence from which to reconstruct the work. Extract every completed activity. Ignore greetings, small talk, scheduling messages, calendar discussions, and meeting links unless they resulted in actual discussed project outcomes. Extract only meaningful project work.
3. DELIVERABLE CONSOLIDATION: Group and combine related activities and actions into broader, professional business deliverables.
4. EXPAND WITH PROFESSIONAL BUSINESS/CONSULTANT LANGUAGE: Do not write simple one-sentence descriptions for a deliverable. Instead, expand each deliverable into professional consultant language detailing the business outcomes.
   Example:
   Instead of:
   Updated brochure.
   Write:
   Developed and finalized the marketing brochure aligned with the client's communication objectives.
   Reviewed brochure structure and messaging based on client feedback.
   Refined visual presentation before final approval.
5. MULTIPLE BULLET POINTS: Every category or deliverable identified in the report must contain multiple detailed bullet points whenever supported by evidence.
6. AUTO-IDENTIFY SECTIONS: Identify the type of project automatically. Create appropriate section names and headings dynamically based on the project context and work performed. Do not select headers from a predefined list.
7. NEVER REPEAT: Never repeat the same work descriptions across sections.
8. BANNED WORDS: Never mention the word "WhatsApp" or "AI" anywhere in the final client report. Also never use any of these phrases or words: "leveraging", "it is worth noting", "it should be noted", "comprehensive", "robust", "seamless", "cutting-edge", "transformative".
9. NO EMOJIS: Do not include emojis in any keys, values, headers, or report content.
10. JSON COMPATIBILITY:
   * Return ONLY valid JSON.
   * Do NOT wrap JSON in markdown (do not output triple backticks or ```json).
   * Escape every newline inside string values as \\n.
   * Escape every backslash correctly (e.g. \\\\).
   * Never output invalid escape sequences.
   * Do NOT include comments.
   * Do NOT include trailing commas in JSON objects or lists.
   * Escape all double quotes inside string values (especially in the "client_report" markdown text) using standard JSON escaping.
11. RECONSTRUCTION CONFIDENCE:
   * The "confidence" field must be an integer (0-100) representing your confidence in this task's reconstruction.
   * The ""confidence_reason" must be a list of 2-4 strings (bullet points) explaining the score based on specific factors (e.g. number of messages, client acknowledgement, consistency, deliverables).
12. EVIDENCE VERIFICATION:
   * Compare the WhatsApp evidence, supporting documents (if provided), and the generated task to set "verification_status" as:
     - "Verified" (supporting document confirms the work described)
     - "Partially Verified" (supporting document confirms only parts)
     - "Contradicted" (supporting document contradicts the task)
     - "Not Verified" (supporting document does not mention the task)
     - "Awaiting Supporting Documents" (if no supporting document content is provided)
13. CONCISENESS & SIZE LIMITS:
   * Keep the "project_summary" under 150 words.
   * Limit the "client_report" to 250-400 words maximum.
   * Do NOT duplicate or repeat information between "project_summary", "completed_tasks.reason", and "client_report".
   * Summarize outcomes in "client_report" instead of listing evidence or tasks.
   * Never repeat information already present in "completed_tasks" inside other sections.
   * Include at most 2 evidence IDs per completed task in "evidence_ids".
   * Avoid repeating the same task in multiple sections.
14. PROJECT INTELLIGENCE:
   * Reconstruct and populate the "project_intelligence" block based on project evidence.
   * Determine "project_health": "status" must be one of "On Track", "Needs Attention", "At Risk", "Blocked", accompanied by a brief "explanation".
   * Generate 3-5 "insights" (evidence-backed observations). For each insight, include "insight" (the statement) and a list "why" containing only the message IDs (e.g. ["MSG_0001", "MSG_0002"]) of supporting messages chronologically.
   * Generate "potential_risks" supported by evidence. If none exist, output "No significant risks detected." as the risk text. For each risk, include "risk" (the statement) and a "why" list containing only the message IDs (e.g. ["MSG_0003"]) of supporting messages.
   * Generate "recommended_next_steps": a list of practical evidence-based next action items.
15. CONSULTING STYLE:
   * Write in the style of a senior project manager or consultant presenting to a client.
   * Use formal but readable English. Active voice where possible.
   * Do not use bullet lists where prose works better.
   * Section headers must match exactly the 7 sections listed above.
   * Client report length: minimum 250 words, maximum 400 words.
{continuity_instruction}

Use EXACTLY this schema:

{{
    "project_summary": "High-level summary of the progress made during this period.",

    "completed_tasks": [
        {{
            "task": "A concise description of the broader completed task/deliverable.",
            "estimated_hours": 0.0,
            "confidence": 85,
            "confidence_reason": [
                "Task discussed across X messages",
                "Client acknowledged completion"
            ],
            "verification_status": "Awaiting Supporting Documents",
            "reason": "Detailed explanation of why this task is considered complete.",
            "evidence_ids": [
                "MSG_0001"
            ]
        }}
    ],

    "pending_tasks": [
        "Description of unresolved or ongoing tasks."
    ],

    "new_requests": [
        "Description of new client requirements or requests raised."
    ],

    "client_report": "A complete, professional consulting-style client-ready report in markdown. Must include exactly 7 sections. Between 250 and 400 words.",

    "project_intelligence": {{
        "project_health": {{
            "status": "On Track",
            "explanation": "Brief explanation of status based on evidence."
        }},
        "insights": [
            {{
                "insight": "Observation statement 1.",
                "why": [
                    "MSG_0001"
                ]
            }}
        ],
        "potential_risks": [
            {{
                "risk": "Risk description 1.",
                "why": [
                    "MSG_0002"
                ]
            }}
        ],
        "recommended_next_steps": [
            "Action recommendation 1"
        ]
    }}
}}
"""