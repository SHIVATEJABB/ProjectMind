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


def analyze_project(prompt):
    """
    Sends the prompt to OpenRouter and returns:
    - parsed JSON
    - raw AI response
    If parsing fails, it automatically retries once with corrective instructions.
    Saves raw response on success or failure for debugging.
    """
    total_start = time.time()
    prompt_len = len(prompt)
    approx_tokens = prompt_len // 4
    
    print("\n========== ENTERED analyze_project ==========\n")
    print(f"[AI LOG] Prompt length: {prompt_len} chars")

    messages = [
        {
            "role": "user",
            "content": prompt
        }
    ]

    api_start = time.time()
    raw_response = ""
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0,
            max_tokens=1800  # Limited output tokens (Part 2)
        )
        raw_response = response.choices[0].message.content
        save_raw_response_debug(raw_response, prompt_len)
    except Exception as api_err:
        print(f"[ERROR] First OpenRouter API call failed: {api_err}")
        raise RuntimeError(f"Network error or timeout calling AI: {str(api_err)}")

    print("\n========== FIRST 300 CHARACTERS OF RESPONSE 1 ==========\n")
    print(raw_response[:300])
    print("\n=======================================================\n")

    try:
        # Check size validation: reject responses exceeding safety character limit
        if len(raw_response) > 15000:
            raise ValueError(f"The response was too large ({len(raw_response)} characters).")
            
        data = extract_json(raw_response)
        total_duration = time.time() - total_start
        print(f"[AI LOG] First parse succeeded in {total_duration:.3f} s")
        return data, raw_response
    except Exception as e:
        print(f"[WARNING] First parse failed or response was too large: {e}. Initiating auto-retry...")
        
        # Save first attempt to debug log
        save_raw_response_debug(raw_response, prompt_len)
        
        # Prepare retry conversation with a stronger instruction to shorten
        messages.append({
            "role": "assistant",
            "content": raw_response
        })
        messages.append({
            "role": "user",
            "content": "The previous response was too large, malformed, or truncated. Shorten the report. Use concise evidence references. Do not quote conversations."
        })

        retry_raw_response = ""
        try:
            retry_response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=0,
                max_tokens=1800  # Limited output tokens (Part 2)
            )
            retry_raw_response = retry_response.choices[0].message.content
            save_raw_response_debug(retry_raw_response, prompt_len)
        except Exception as retry_api_err:
            print(f"[ERROR] Retry API call failed: {retry_api_err}")
            raise ValueError(f"AI returned malformed response and retry failed due to network error: {str(retry_api_err)}")

        print("\n========== FIRST 300 CHARACTERS OF RETRY RESPONSE ==========\n")
        print(retry_raw_response[:300])
        print("\n============================================================\n")

        try:                
            data = extract_json(retry_raw_response)
            total_duration = time.time() - total_start
            print(f"[AI LOG] Retry parse succeeded in {total_duration:.3f} s")
            return data, retry_raw_response
        except Exception as retry_err:
            print(f"[ERROR] Retry parse failed: {retry_err}")
            save_raw_response_debug(retry_raw_response, prompt_len)
            
            # Raise detailed error message based on failure cause (Part 7)
            err_msg = str(retry_err)
            if "truncated" in err_msg.lower():
                raise ValueError("The AI response exceeded the maximum length and was truncated.")
            elif "malformed" in err_msg.lower():
                raise ValueError("The AI returned malformed JSON after retry.")
            else:
                raise ValueError(f"AI generated an invalid response: {err_msg}")