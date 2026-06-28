import json
import os
import time
import datetime

from config import client, MODEL_NAME


def repair_json_string(s):
    """
    Attempts to repair lightweight formatting errors in a JSON string:
    - Normalizes line endings to \n
    - Replaces smart quotes (“ ” and ‘ ’) with standard quotes
    - Removes invalid control characters (ASCII 0-31 except \n, \t, \r)
    - Repairs invalid escape sequences
    - Escapes unescaped newlines and tabs inside JSON string values
    - Safely removes trailing commas before closing braces/brackets outside strings
    """
    import re
    # Normalize line endings
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    
    # Replace smart quotes with standard quotes
    s = s.replace("“", '"').replace("”", '"')
    s = s.replace("‘", "'").replace("’", "'")
    
    chars = list(s)
    n = len(chars)
    result = []
    in_string = False
    i = 0
    
    while i < n:
        c = chars[i]
        
        if c == '"':
            # Check if it is escaped in result
            bs_count = 0
            j = len(result) - 1
            while j >= 0 and result[j] == '\\':
                bs_count += 1
                j -= 1
            if bs_count % 2 == 0:
                in_string = not in_string
            result.append(c)
            i += 1
        elif c == '\\':
            if i + 1 < n:
                next_c = chars[i + 1]
                if next_c in ['"', '\\', '/', 'b', 'f', 'n', 'r', 't']:
                    result.append('\\')
                    result.append(next_c)
                    i += 2
                elif next_c == 'u':
                    if i + 5 < n and all(ch in '0123456789abcdefABCDEF' for ch in chars[i+2:i+6]):
                        result.append('\\')
                        result.append('u')
                        for k in range(4):
                            result.append(chars[i+2+k])
                        i += 6
                    else:
                        result.append('\\\\')
                        result.append('u')
                        i += 2
                else:
                    result.append('\\\\')
                    result.append(next_c)
                    i += 2
            else:
                result.append('\\\\')
                i += 1
        else:
            if ord(c) < 32:
                if in_string:
                    if c == '\n':
                        result.append('\\')
                        result.append('n')
                    elif c == '\t':
                        result.append('\\')
                        result.append('t')
                    elif c == '\r':
                        result.append('\\')
                        result.append('r')
                else:
                    if c in [' ', '\t', '\n', '\r']:
                        result.append(c)
                i += 1
            elif c == ',' and not in_string:
                look_idx = i + 1
                is_trailing = False
                while look_idx < n:
                    next_char = chars[look_idx]
                    if next_char in [' ', '\t', '\n', '\r']:
                        look_idx += 1
                    elif next_char in ['}', ']']:
                        is_trailing = True
                        break
                    else:
                        break
                if is_trailing:
                    i += 1
                    continue
                else:
                    result.append(c)
                    i += 1
            else:
                result.append(c)
                i += 1
                
    return "".join(result)


def save_raw_response_debug(raw_text, prompt_size):
    """
    Saves the raw response to last_response.txt with timestamp and size metadata.
    """
    path = os.path.join(os.getcwd(), "last_response.txt")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("--- Debug Metadata ---\n")
            f.write(f"Timestamp: {datetime.datetime.now().isoformat()}\n")
            f.write(f"Model Name: {MODEL_NAME}\n")
            f.write(f"Prompt Size: {prompt_size} characters\n")
            f.write(f"Response Size: {len(raw_text)} characters\n")
            f.write("----------------------\n\n")
            f.write(raw_text)
    except Exception as e:
        print(f"[ERROR] Failed to save raw response debug: {e}")


def extract_json(text):
    """
    Extracts and parses the JSON object from the response text.
    Validates schema and forces fallback defaults if optional keys are missing.
    """
    text = text.replace("```json", "")
    text = text.replace("```", "")
    text = text.strip()

    # Detect truncated JSON (Part 4)
    if not text.endswith("}"):
        raise ValueError("The AI response was truncated before the JSON completed.")

    start_idx = text.find("{")
    end_idx = text.rfind("}")

    if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
        json_str = text[start_idx:end_idx + 1]

        data = None
        # Try loading valid JSON first
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            # Attempt repair (Part 6)
            repaired_str = repair_json_string(json_str)
            try:
                data = json.loads(repaired_str)
            except json.JSONDecodeError as e:
                raise ValueError(f"The AI returned malformed JSON: {str(e)}")

        if data is not None:
            # Validate schema and fill defaults (Part 5)
            if not isinstance(data, dict):
                raise ValueError("The AI response was not a dictionary object.")
                
            required_keys = ["project_summary", "completed_tasks", "pending_tasks", "new_requests", "client_report", "project_intelligence"]
            for key in required_keys:
                if key not in data:
                    if key in ["completed_tasks", "pending_tasks", "new_requests"]:
                        data[key] = []
                    elif key == "project_intelligence":
                        data[key] = {
                            "project_health": {"status": "On Track", "explanation": "No health status determined."},
                            "insights": [],
                            "potential_risks": [],
                            "recommended_next_steps": []
                        }
                    else:
                        data[key] = ""
            return data

    raise ValueError("No JSON object found in response.")


def extract_reconstruction_state(text):
    """
    Extracts the Stage 1 project state JSON response.
    """
    text = text.replace("```json", "")
    text = text.replace("```", "")
    text = text.strip()
    
    start_idx = text.find("{")
    end_idx = text.rfind("}")
    
    if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
        json_str = text[start_idx:end_idx + 1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            repaired = repair_json_string(json_str)
            return json.loads(repaired)
            
    raise ValueError("No project state JSON found in Stage 1 response.")


def analyze_project(prompt):
    """
    Sends the prompt to OpenRouter using a model-agnostic two-stage pipeline:
    1. Project Reconstruction: Extracts compact project state from raw evidence.
    2. Report Writing: Formats the state into a polished, dynamic report.
    """
    total_start = time.time()
    
    # 1. Parse serialized prompt parameters
    try:
        params = json.loads(prompt)
        project_name = params["project_name"]
        client_name = params["client_name"]
        start_date = params["start_date"]
        end_date = params["end_date"]
        evidence = params["project_evidence"]
        previous_report_data = params.get("previous_report_data")
    except Exception:
        # Fallback if standard string is passed
        project_name = "Project"
        client_name = "Client"
        start_date = ""
        end_date = ""
        evidence = prompt
        previous_report_data = None
        
    print("\n========== ENTERED analyze_project (Model-Agnostic Two-Stage) ==========\n")
    from prompts import build_reconstruction_prompt, build_writer_prompt
    
    # --- STAGE 1: Reconstruction / State Creation ---
    reconstruction_prompt = build_reconstruction_prompt(
        project_name, client_name, start_date, end_date, evidence, previous_report_data
    )
    
    print(f"[AI LOG Stage 1] Reconstruction prompt length: {len(reconstruction_prompt)} chars")
    
    api_messages_1 = [
        {"role": "user", "content": reconstruction_prompt}
    ]
    
    try:
        response_1 = client.chat.completions.create(
            model=MODEL_NAME,
            messages=api_messages_1,
            temperature=0,
            max_tokens=1500
        )
        raw_state_response = response_1.choices[0].message.content
    except Exception as e:
        print(f"[ERROR] Stage 1 API call failed: {e}")
        raise RuntimeError(f"Network error in Stage 1 Project Reconstruction: {str(e)}")
        
    try:
        project_state = extract_reconstruction_state(raw_state_response)
    except Exception as e:
        print(f"[WARNING] Stage 1 parsing failed, attempting retry: {e}")
        api_messages_1.append({"role": "assistant", "content": raw_state_response})
        api_messages_1.append({"role": "user", "content": "The previous response was malformed or incomplete. Return ONLY a valid JSON object matching the requested completed_activities schema."})
        
        try:
            response_1_retry = client.chat.completions.create(
                model=MODEL_NAME,
                messages=api_messages_1,
                temperature=0,
                max_tokens=1500
            )
            raw_state_response = response_1_retry.choices[0].message.content
            project_state = extract_reconstruction_state(raw_state_response)
        except Exception as retry_err:
            print(f"[ERROR] Stage 1 retry failed: {retry_err}")
            raise ValueError(f"Project Reconstruction failed to extract valid state: {str(retry_err)}")
            
    # --- STAGE 2: Report Writing ---
    writer_prompt = build_writer_prompt(
        project_name, client_name, start_date, end_date, project_state
    )
    
    print(f"[AI LOG Stage 2] Writer prompt length: {len(writer_prompt)} chars")
    
    api_messages_2 = [
        {"role": "user", "content": writer_prompt}
    ]
    
    try:
        response_2 = client.chat.completions.create(
            model=MODEL_NAME,
            messages=api_messages_2,
            temperature=0,
            max_tokens=2500
        )
        raw_writer_response = response_2.choices[0].message.content
        save_raw_response_debug(raw_writer_response, len(writer_prompt))
    except Exception as e:
        print(f"[ERROR] Stage 2 API call failed: {e}")
        raise RuntimeError(f"Network error in Stage 2 Report Writing: {str(e)}")
        
    try:
        data = extract_json(raw_writer_response)
        total_duration = time.time() - total_start
        print(f"[AI LOG] Two-stage pipeline completed in {total_duration:.3f} s")
        return data, raw_writer_response
    except Exception as e:
        print(f"[WARNING] Stage 2 parsing failed, attempting retry: {e}")
        api_messages_2.append({"role": "assistant", "content": raw_writer_response})
        api_messages_2.append({"role": "user", "content": "The previous response was malformed or truncated. Shorten the report. Use concise formatting. Return ONLY valid JSON."})
        
        try:
            response_2_retry = client.chat.completions.create(
                model=MODEL_NAME,
                messages=api_messages_2,
                temperature=0,
                max_tokens=2500
            )
            raw_writer_response = response_2_retry.choices[0].message.content
            save_raw_response_debug(raw_writer_response, len(writer_prompt))
            data = extract_json(raw_writer_response)
            total_duration = time.time() - total_start
            print(f"[AI LOG] Two-stage pipeline retry succeeded in {total_duration:.3f} s")
            return data, raw_writer_response
        except Exception as retry_err:
            print(f"[ERROR] Stage 2 retry failed: {retry_err}")
            raise ValueError(f"Report Generation failed to output valid JSON: {str(retry_err)}")