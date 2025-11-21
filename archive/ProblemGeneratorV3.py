import os
import sys
import traceback
import google.generativeai as genai
api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    raise RuntimeError("Missing GOOGLE_API_KEY environment variable. Set it before running.")
genai.configure(api_key=api_key)
llm = genai.GenerativeModel('gemini-2.5-flash')

from prompts import *
import json
import math
import datetime


# Takes in a Question-Solution Pair and generates a Single Word Problem. 
# (ProblemGeneratorV3.py will generate 3-5 Problem)

################################################################################################################
# Functions

# Function for Reading JSON data from files
def inner_load_json_from_file(filename):
    # Determine the base directory. This correctly handles cases where
    # the script is run from a different directory or is part of a package.
    # If __file__ is not available (e.g., in an interactive session), use os.getcwd().
    current_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else os.getcwd()
    filepath = os.path.join(current_dir, filename)

    print(f"Attempting to open: {filepath}") # Added for debugging

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    # Convert the loaded Python dict back to a JSON string for the prompt
    return json.dumps(data, indent=2) # Use indent for readability for the LLM

def load_json_from_file(filename):
    try:
        return inner_load_json_from_file(filename)
    except FileNotFoundError as e:
        print(f"Error loading JSON file: {e}")
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from file: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

#Parsing JSON output from LLM CALL 
def llm_op_to_json(op_call1):
    cleaned_json_string = op_call1.text.strip()
    if cleaned_json_string.startswith("```json"):
        cleaned_json_string = cleaned_json_string[len("```json"):].strip()
    if cleaned_json_string.endswith("```"):
        cleaned_json_string = cleaned_json_string[:-len("```")].strip()
    # Now parse the cleaned string
    try:
        op_call1_data = json.loads(cleaned_json_string)
        # print("\nSuccessfully parsed LLM output JSON:")
        # print(json.dumps(op_call1_data, indent=2)) # Pretty print for verification
        # print("\nAccessing a specific part, e.g., relevant_chapters:")
        # print(op_call1_data["relevant_chapters"])
        return op_call1_data
    except json.JSONDecodeError as e:
        print("=========================================================================")
        print(f"Error after cleaning: JSONDecodeError: {e}")
        print("Problematic string content:")
        print(f"'{cleaned_json_string[:500]}...'") # Print start of problematic string
    except Exception as e:
        print("=========================================================================")
        print(f"An unexpected error occurred while parsing cleaned LLM output: {e}")
        traceback.print_exc()


# --- Helpers (added) ---
def normalize_available_formula_ids(available_formulas):
    """
    Return (set_of_ids, map_id_to_formula).
    Handles cases where available_formulas values are lists of dicts or dicts.
    """
    ids = set()
    by_id = {}
    if not isinstance(available_formulas, dict):
        return ids, by_id
    for key, val in available_formulas.items():
        if isinstance(val, dict):
            # try to extract nested items
            for subk, subv in val.items():
                if isinstance(subv, dict) and 'formula_id' in subv:
                    fid = subv['formula_id']
                    ids.add(fid)
                    by_id[fid] = subv
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    fid = item.get('formula_id')
                    if fid:
                        ids.add(fid)
                        by_id[fid] = item
    print(f"normalize_available_formula_ids: found {len(ids)} formula ids")
    return ids, by_id


def compute_problem_signature(op_call2_data):
    """
    Simple canonical signature: sorted formula_ids + unknown_var.
    Example: 'fids=[F1,F2]|unknown=vx'
    """
    fids = op_call2_data.get('formula_ids', []) or []
    try:
        sorted_fids = sorted([str(x) for x in fids])
    except Exception:
        sorted_fids = [str(x) for x in fids]
    unknown = None
    for k, v in (op_call2_data.get('variables', {}) or {}).items():
        if str(v.get('value')).lower() == 'nan':
            unknown = k
            break
    sig = f"fids=[{','.join(sorted_fids)}]|unknown={unknown}"
    print(f"compute_problem_signature: {sig}")
    return sig


def format_previous_problems_for_prompt(previous_problems, max_items=5):
    """
    Return a compact JSON string (array) containing recent signatures.
    """
    compact = []
    for p in previous_problems[:max_items]:
        compact.append({
            "signature": p.get("signature"),
            "snippet": p.get("snippet", "")[:140]
        })
    s = json.dumps(compact, indent=2)
    print(f"format_previous_problems_for_prompt: passing {len(compact)} previous signatures")
    return s


def sanitize_code_text(code_text):
    """
    Strip triple-backtick fences and language tags, return the full LLM output code.
    If fenced blocks are present, prefer a fenced block that looks like code; otherwise
    return the entire trimmed output.
    """
    if not isinstance(code_text, str):
        return code_text
    s = code_text.strip()
    if '```' in s:
        parts = s.split('```')
        # Prefer a fenced block that appears to contain python code
        for part in parts:
            part_strip = part.strip()
            if not part_strip:
                continue
            if part_strip.startswith('def ') or part_strip.startswith('import') or 'def solve' in part_strip:
                print("sanitize_code_text: extracted fenced code block")
                return part_strip
        # Fallback to the first fenced block content
        if len(parts) >= 2:
            print("sanitize_code_text: extracted first fenced block")
            return parts[1].strip()
    # No fences: return entire trimmed output
    print("sanitize_code_text: returning full trimmed LLM output")
    return s


def validate_problem(output, formula_dict, variable_ranges, previous_problems):
    # Normalize formula_dict to a set of ids
    if isinstance(formula_dict, dict):
        formula_id_set = set(formula_dict.keys())
    else:
        try:
            formula_id_set = set(formula_dict)
        except Exception:
            formula_id_set = set()

    # Check 1: All formula_ids exist
    if not all(fid in formula_id_set for fid in output.get("formula_ids", [])):
        return {"valid": False, "error": "Invalid formula_id"}

    # Check 2: Exactly one NaN variable
    nan_vars = [k for k, v in output.get("variables", {}).items() if str(v.get("value")).lower() == "nan"]
    if len(nan_vars) != 1:
        return {"valid": False, "error": f"Must have exactly 1 unknown, found {len(nan_vars)}"}

    unknown_var = nan_vars[0]

    # Check 3: Values within specified ranges
    for var_name, var_data in output.get("variables", {}).items():
        if str(var_data.get("value")).lower() != "nan":
            if var_name in variable_ranges:
                rr = variable_ranges[var_name].get("range") if isinstance(variable_ranges[var_name], dict) else None
                if rr and isinstance(rr, (list, tuple)) and len(rr) == 2:
                    range_min, range_max = rr
                    try:
                        actual_value = float(var_data.get("value"))
                    except (ValueError, TypeError):
                        return {"valid": False, "error": f"Variable '{var_name}' has an invalid numerical value: '{var_data.get('value')}'."}
                    if not (range_min <= actual_value <= range_max):
                        return {"valid": False, "error": f"{var_name} with value {actual_value} is out of expected range [{range_min}, {range_max}]."}

    # Check 4: Uniqueness using problem signature (simple: formulas + unknown)
    try:
        current_signature = compute_problem_signature(output)
        for prev_problem in previous_problems:
            if prev_problem.get("signature") == current_signature:
                return {"valid": False, "error": "Duplicate problem signature"}
    except Exception:
        # if something goes wrong computing signature, skip uniqueness check
        pass

    return {"valid": True, "unknown_var": unknown_var}


def execute_and_validate_in_repl(code, variables):
    # Step 1: Execute code safely in isolated namespace
    repl_globals = {}
    try:
        exec(code, repl_globals)
        if 'solve' not in repl_globals or not callable(repl_globals['solve']):
            return {"valid": False, "error": "'solve()' function not found", "result": None}
        result = repl_globals['solve']()
    except Exception as e:
        return {"valid": False, "error": f"Execution failed: {str(e)}", "result": None}
    
    # Step 2: Validate result type and numeric value
    if result is None or not isinstance(result, (int, float)):
        return {"valid": False, "error": "Invalid return type", "result": None}
    if math.isnan(result) or math.isinf(result):
        return {"valid": False, "error": "Result is NaN or Inf", "result": None}
    
    # Step 3: Basic physical sanity check
    unknown_vars = [k for k, v in variables.items() if str(v["value"]).lower() == "nan"]
    if unknown_vars:
        unknown_var = unknown_vars[0]
        if result < 0 and any(x in unknown_var.lower() for x in ["mass", "distance", "time", "speed", "velocity", "energy"]):
            return {"valid": False, "error": f"Negative value for {unknown_var}", "result": result}
    
    # Step 4: If all checks pass
    return {"valid": True, "result": result}


################################################################################################################

# [[[LLM CALL 1]]] #

print(" Start ---------------------------------------------------------------------------- \n ")
chapters_json = load_json_from_file('codebase_main/chapter_manifest.json')

op_call1 = llm.generate_content(sys_call1.format(
    chapters_json = chapters_json,
    question= question,
    solution= solution
))

print(op_call1.text)
op_call1_data = llm_op_to_json(op_call1)

# [[[ACTION 1]]] # Analyse Problems to get Relevant Chapters, Variables and Alternate Scenarios

# Trying to Get identified_chapters
identified_chapters = op_call1_data['relevant_chapters']

# Trying to make "available_formulas" from identified_chapters
available_formulas = {}
for item in identified_chapters: 
    temp_file = load_json_from_file('codebase_main/'+item+'.json')
    temp_data = json.loads(temp_file)
    available_formulas.update(temp_data)

formulas_json = json.dumps(available_formulas, indent=2)

# temp_file = load_json_from_file('codebase_main/'+identified_chapters[0]+'.json')
# temp_data = json.loads(temp_file)
# available_formulas.update(temp_data)

# formulas_json = json.dumps(available_formulas, indent=2)
# print("Available Formulas:")
# print(formulas_json)

# temp_file = load_json_from_file('codebase_main/'+identified_chapters[1]+'.json')
# temp_data = json.loads(temp_file)
# available_formulas.update(temp_data)

# formulas_json = json.dumps(available_formulas, indent=2)
# print("Available Formulas:")
# print(formulas_json)

print("Call 1 Completed---------------------------------------------------------------------------- \n ")

################################################################################################################

# [[[LLM CALL 1A]]] # Check if Formulas are sufficient Against the Solution

op_call1a = llm.generate_content(sys_call1a.format(
    solution= solution,
    identified_chapters= json.dumps(identified_chapters, indent=2),
    available_formulas= formulas_json,
    all_chapters_json= chapters_json
))

print(op_call1a.text)
op_call1a_data = llm_op_to_json(op_call1a)

# [[[ACTION 1A]]] # Update identified chapters if formulas are insufficient 
# \\ Should this be in a loop until status is "YES" or max 2 iterations reached?

# if op_call2_data['status'] == "NO": then adding the missing chapter to identified chapters
if op_call1a_data.get('status') == "NO":
    missing_chapter = op_call1a_data.get('missing_chapter')
    if missing_chapter and missing_chapter not in identified_chapters:
        identified_chapters.append(missing_chapter)
        print(f"Added missing chapter: {missing_chapter} to identified chapters.")

        # Updating available_formulas after adding missing chapter
        temp_file = load_json_from_file('codebase_main/'+missing_chapter+'.json')
        temp_data = json.loads(temp_file)
        available_formulas.update(temp_data)

        print("Updated available_formulas after adding missing chapter.")
        print(json.dumps(available_formulas, indent=2))


print("Call 1A Completed---------------------------------------------------------------------------- \n ")

#################################################################################################################

# --- Multi-problem generation loop (replaces single-run Call2/Call3 sequence) ---

# Configure loop parameters
max_iterations = 5
target_problems = 3
current_iteration = 0
successful_problems = []
previous_problems = []  # list of dicts with keys: signature, snippet, created_at

# Normalize available formulas for validation
formula_id_set, available_by_id = normalize_available_formula_ids(available_formulas)

print("Starting multi-problem generation loop...")
while current_iteration < max_iterations and len(successful_problems) < target_problems:
    current_iteration += 1
    print(f"\n--- Iteration {current_iteration} ---")
    # Prepare compact previous_problems payload for prompt
    prev_for_prompt = format_previous_problems_for_prompt(previous_problems, max_items=5)

    # Call 2: Word Problem Generation (first attempt)
    try:
        op_call2 = llm.generate_content(sys_call2.format(
            available_formulas = json.dumps(available_formulas, indent=2),
            alternate_scenarios = json.dumps(op_call1_data.get('alternate_scenarios', []), indent=2),
            variables = json.dumps(op_call1_data.get('variables', {}), indent=2),
            previous_problems = prev_for_prompt
        ))
    except Exception as e:
        print(f"Call 2 generation failed: {e}. Skipping iteration.")
        continue

    print("Call2 output (raw):")
    print(op_call2.text if hasattr(op_call2, 'text') else str(op_call2))

    op_call2_data = llm_op_to_json(op_call2)
    # If parse failed, retry once using sys_call2a format (if available)
    if not op_call2_data:
        print("Call2 parse failed; retrying once with error hint.")
        try:
            op_call2a = llm.generate_content(sys_call2a.format(
                error_message = "Parsing failure from previous response.",
                available_formulas = json.dumps(available_formulas, indent=2),
                alternate_scenarios = json.dumps(op_call1_data.get('alternate_scenarios', []), indent=2),
                variables = json.dumps(op_call1_data.get('variables', {}), indent=2),
                previous_problems = prev_for_prompt
            ))
        except Exception as e:
            print(f"Call2 retry failed to generate: {e}. Skipping iteration.")
            continue
        op_call2_data = llm_op_to_json(op_call2a)
        if not op_call2_data:
            print("Call2 retry parse also failed. Skipping iteration.")
            continue

    # Validate the problem
    validation_result = validate_problem(
        output=op_call2_data,
        formula_dict=formula_id_set,
        variable_ranges=op_call1_data.get('variables', {}),
        previous_problems = previous_problems
    )
    print(f"Validation Result: {validation_result}")

    # If invalid, retry call2 once with error message
    if not validation_result.get("valid", False):
        error_message = validation_result.get("error", "Unknown validation error")
        print(f"Validation failed: {error_message}. Retrying Call 2 once.")
        try:
            op_call2b = llm.generate_content(sys_call2a.format(
                error_message = error_message,
                available_formulas = json.dumps(available_formulas, indent=2),
                alternate_scenarios = json.dumps(op_call1_data.get('alternate_scenarios', []), indent=2),
                variables = json.dumps(op_call1_data.get('variables', {}), indent=2),
                previous_problems = prev_for_prompt
            ))
        except Exception as e:
            print(f"Call2 retry generation exception: {e}. Skipping iteration.")
            continue
        op_call2_data = llm_op_to_json(op_call2b)
        if not op_call2_data:
            print("Call2 retry parse failed. Skipping iteration.")
            continue
        validation_result = validate_problem(
            output=op_call2_data,
            formula_dict=formula_id_set,
            variable_ranges=op_call1_data.get('variables', {}),
            previous_problems = previous_problems
        )
        print(f"Validation Result after retry: {validation_result}")
        if not validation_result.get("valid", False):
            print("Validation retry failed. Skipping iteration.")
            continue

    # Passed validation; compute signature and check duplicates
    signature = compute_problem_signature(op_call2_data)
    if any(p.get('signature') == signature for p in previous_problems):
        print("Generated problem is duplicate of previous problems. Skipping.")
        continue

    # Call 3: Code generation and execution
    try:
        op_call3 = llm.generate_content(sys_call3.format(
            word_problem = op_call2_data.get('word_problem', ''),
            formula_ids = json.dumps(op_call2_data.get('formula_ids', []), indent=2),
            variables_dict = json.dumps(op_call2_data.get('variables', {}), indent=2),
            available_formulas = json.dumps(available_formulas, indent=2)
        ))
    except Exception as e:
        print(f"Call 3 generation failed: {e}. Skipping iteration.")
        continue

    print("Call3 raw output:")
    print(op_call3.text if hasattr(op_call3, 'text') else str(op_call3))

    code_text = sanitize_code_text(op_call3.text if hasattr(op_call3, 'text') else str(op_call3))
    action3_result = execute_and_validate_in_repl(code_text, op_call2_data.get('variables', {}))
    print(f"Execution result: {action3_result}")

    # Retry once on execution failure
    if not action3_result.get("valid", False):
        err_msg = action3_result.get("error", "Execution failed")
        print(f"Execution failed: {err_msg}. Retrying Call 3 once with feedback.")
        try:
            op_call3a = llm.generate_content(sys_call3a.format(
                error_message = err_msg,
                word_problem = op_call2_data.get('word_problem', ''),
                formula_ids = json.dumps(op_call2_data.get('formula_ids', []), indent=2),
                variables_dict = json.dumps(op_call2_data.get('variables', {}), indent=2),
                available_formulas = json.dumps(available_formulas, indent=2)
            ))
        except Exception as e:
            print(f"Call3 retry generation failed: {e}. Skipping iteration.")
            continue
        code_text = sanitize_code_text(op_call3a.text if hasattr(op_call3a, 'text') else str(op_call3a))
        action3_result = execute_and_validate_in_repl(code_text, op_call2_data.get('variables', {}))
        print(f"Execution result after retry: {action3_result}")
        if not action3_result.get("valid", False):
            print("Call3 retry failed. Skipping iteration.")
            continue

    # Success: record problem
    now = datetime.datetime.utcnow().isoformat()
    successful_record = {
        "signature": signature,
        "formula_ids": op_call2_data.get('formula_ids', []),
        "unknown_var": validation_result.get('unknown_var'),
        "word_problem": op_call2_data.get('word_problem', ''),
        "variables": op_call2_data.get('variables', {}),
        "code": code_text,
        "answer": action3_result.get('result'),
        "execution_result": action3_result,
        "validation_result": validation_result,
        "created_at": now
    }
    successful_problems.append(successful_record)
    # add to previous_problems (newest-first)
    previous_problems.insert(0, {
        "signature": signature,
        "snippet": op_call2_data.get('word_problem', '')[:140],
        "created_at": now
    })
    # trim previous_problems
    previous_problems = previous_problems[:10]
    print(f"Recorded successful problem #{len(successful_problems)}")

print("\nMulti-problem generation loop completed.")
print(f"Iterations: {current_iteration}, Successful: {len(successful_problems)}")
# Optionally persist successful_problems to a file
try:
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'successful_problems.json'), 'w', encoding='utf-8') as f:
        json.dump(successful_problems, f, indent=2)
    print("Saved successful problems to 'successful_problems.json'")
except Exception as e:
    print(f"Could not save successful_problems.json: {e}")