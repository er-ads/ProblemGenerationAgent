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

# Import helpers extracted to pg_helpers.py
from pg_helpers import (
    load_json_from_file,
    llm_op_to_json,
    normalize_available_formula_ids,
    compute_problem_signature,
    format_previous_problems_for_prompt,
    sanitize_code_text,
    validate_problem,
    execute_and_validate_in_repl,
    atomic_write_json,
)

# ProblemGeneratorV5: concise runner that preserves the same logic as V4
# Phases: Call1 (analyze Q/S) -> Call1A (check formulas) -> build available_formulas ->
# multi-iteration loop: round-robin over alternate_scenarios with two cycles per iteration ->
# Call2 (word problem) + validation (retry once) -> Call3 (code) + exec (retry once) -> record -> merge write

print(" Start ---------------------------------------------------------------------------- \n ")
chapters_json = load_json_from_file('codebase_main/chapter_manifest.json')

# CALL 1: Ask LLM to analyze the question/solution pair and propose relevant chapters, variables, and alternate scenarios
op_call1 = llm.generate_content(sys_call1.format(
    chapters_json = chapters_json,
    question= question5a,
    solution= solution5a
))

print(op_call1.text)
op_call1_data = llm_op_to_json(op_call1)

# ACTION 1: collect identified chapters and build available_formulas
identified_chapters = op_call1_data['relevant_chapters']
available_formulas = {}
for item in identified_chapters:
    temp_file = load_json_from_file('codebase_main/'+item+'.json')
    temp_data = json.loads(temp_file)
    available_formulas.update(temp_data)

formulas_json = json.dumps(available_formulas, indent=2)

print("Call 1 Completed---------------------------------------------------------------------------- \n ")

# CALL 1A: Verify formulas are sufficient for the provided solution
op_call1a = llm.generate_content(sys_call1a.format(
    solution= solution,
    identified_chapters= json.dumps(identified_chapters, indent=2),
    available_formulas= formulas_json,
    all_chapters_json= chapters_json
))

print(op_call1a.text)
op_call1a_data = llm_op_to_json(op_call1a)

# If Call1A reports a missing chapter, add it and update available_formulas
if op_call1a_data.get('status') == "NO":
    missing_chapter = op_call1a_data.get('missing_chapter')
    if missing_chapter and missing_chapter not in identified_chapters:
        identified_chapters.append(missing_chapter)
        temp_file = load_json_from_file('codebase_main/'+missing_chapter+'.json')
        temp_data = json.loads(temp_file)
        available_formulas.update(temp_data)

print("Call 1A Completed---------------------------------------------------------------------------- \n ")

# --- Multi-problem generation loop (Option B: round-robin, 2 cycles per iteration) ---
# Loop configuration (per user request)
max_iterations = 12
target_problems = 10
current_iteration = 0
successful_problems = []
previous_problems = []  # list of dicts with keys: signature, snippet, created_at

# Normalize available formulas for validation
formula_id_set, available_by_id = normalize_available_formula_ids(available_formulas)

# Load existing successful problems to merge later
existing_records = []
success_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'successful_problems.json')
if os.path.exists(success_file_path):
    try:
        with open(success_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                existing_records = data
            else:
                print("Warning: existing successful_problems.json is not a list; will be overwritten at end.")
    except Exception as e:
        print(f"Warning: could not read existing successful_problems.json: {e}. Will overwrite at end.")

alternate_scenarios = op_call1_data.get('alternate_scenarios', []) or []
if not alternate_scenarios:
    print("Warning: no alternate_scenarios returned by Call1; loop will still run but won't rotate scenarios.")

scenario_idx = 0

# Diagnostics counters
total_cycles_attempted = 0
duplicates_skipped = 0
parse_failures = 0
execution_failures = 0

print("Starting multi-problem generation loop (round-robin over scenarios)...")
while current_iteration < max_iterations and len(successful_problems) < target_problems:
    current_iteration += 1
    print(f"\n--- Iteration {current_iteration} ---")

    # Pick scenario round-robin (single scenario wrapped in a list when passed to Call2)
    selected_scenario = None
    if alternate_scenarios:
        try:
            selected_scenario = alternate_scenarios[scenario_idx % len(alternate_scenarios)]
        except Exception:
            selected_scenario = alternate_scenarios[0]
        scenario_idx += 1

    # Run two independent cycles for this selected scenario
    for cycle_no in range(2):
        total_cycles_attempted += 1
        print(f" Cycle {cycle_no+1} for scenario index {scenario_idx-1}")
        prev_for_prompt = format_previous_problems_for_prompt(previous_problems, max_items=5)

        if selected_scenario is not None:
            alt_payload = json.dumps([selected_scenario], indent=2)
        else:
            alt_payload = json.dumps([], indent=2)

        # CALL 2: generate candidate word problem
        try:
            op_call2 = llm.generate_content(sys_call2.format(
                available_formulas = json.dumps(available_formulas, indent=2),
                alternate_scenarios = alt_payload,
                variables = json.dumps(op_call1_data.get('variables', {}), indent=2),
                previous_problems = prev_for_prompt
            ))
        except Exception as e:
            print(f" Call2 generation failed: {e}. Skipping this cycle.")
            parse_failures += 1
            continue

        print(" Call2 output (raw):")
        print(op_call2.text if hasattr(op_call2, 'text') else str(op_call2))

        op_call2_data = llm_op_to_json(op_call2)
        # Retry once on parse failure
        if not op_call2_data:
            print(" Call2 parse failed; retrying once with error hint.")
            parse_failures += 1
            try:
                op_call2a = llm.generate_content(sys_call2a.format(
                    error_message = "Parsing failure from previous response.",
                    available_formulas = json.dumps(available_formulas, indent=2),
                    alternate_scenarios = alt_payload,
                    variables = json.dumps(op_call1_data.get('variables', {}), indent=2),
                    previous_problems = prev_for_prompt
                ))
            except Exception as e:
                print(f" Call2 retry generation failed: {e}. Skipping this cycle.")
                continue
            op_call2_data = llm_op_to_json(op_call2a)
            if not op_call2_data:
                print(" Call2 retry parse also failed. Skipping this cycle.")
                parse_failures += 1
                continue

        # Validate the generated problem
        validation_result = validate_problem(
            output=op_call2_data,
            formula_dict=formula_id_set,
            variable_ranges=op_call1_data.get('variables', {}),
            previous_problems = previous_problems
        )
        print(f" Validation Result: {validation_result}")

        # If invalid, retry Call2 once with feedback
        if not validation_result.get('valid', False):
            error_message = validation_result.get('error', 'Unknown validation error')
            print(f" Validation failed: {error_message}. Retrying Call2 once.")
            try:
                op_call2b = llm.generate_content(sys_call2a.format(
                    error_message = error_message,
                    available_formulas = json.dumps(available_formulas, indent=2),
                    alternate_scenarios = alt_payload,
                    variables = json.dumps(op_call1_data.get('variables', {}), indent=2),
                    previous_problems = prev_for_prompt
                ))
            except Exception as e:
                print(f" Call2 retry generation exception: {e}. Skipping this cycle.")
                parse_failures += 1
                continue
            op_call2_data = llm_op_to_json(op_call2b)
            if not op_call2_data:
                print(" Call2 retry parse failed. Skipping this cycle.")
                parse_failures += 1
                continue
            validation_result = validate_problem(
                output=op_call2_data,
                formula_dict=formula_id_set,
                variable_ranges=op_call1_data.get('variables', {}),
                previous_problems = previous_problems
            )
            print(f" Validation Result after retry: {validation_result}")
            if not validation_result.get('valid', False):
                print(" Validation retry failed. Skipping this cycle.")
                parse_failures += 1
                continue

        # Check duplicate signature against previous_problems
        signature = compute_problem_signature(op_call2_data)
        if any(p.get('signature') == signature for p in previous_problems):
            print(" Generated problem is duplicate of previous problems. Skipping this cycle.")
            duplicates_skipped += 1
            continue

        # CALL 3: code generation
        try:
            op_call3 = llm.generate_content(sys_call3.format(
                word_problem = op_call2_data.get('word_problem', ''),
                formula_ids = json.dumps(op_call2_data.get('formula_ids', []), indent=2),
                variables_dict = json.dumps(op_call2_data.get('variables', {}), indent=2),
                available_formulas = json.dumps(available_formulas, indent=2)
            ))
        except Exception as e:
            print(f" Call3 generation failed: {e}. Skipping this cycle.")
            execution_failures += 1
            continue

        print(" Call3 raw output:")
        print(op_call3.text if hasattr(op_call3, 'text') else str(op_call3))

        code_text = sanitize_code_text(op_call3.text if hasattr(op_call3, 'text') else str(op_call3))
        action3_result = execute_and_validate_in_repl(code_text, op_call2_data.get('variables', {}))
        print(f" Execution result: {action3_result}")

        # Retry once on execution failure
        if not action3_result.get('valid', False):
            err_msg = action3_result.get('error', 'Execution failed')
            print(f" Execution failed: {err_msg}. Retrying Call3 once with feedback.")
            try:
                op_call3a = llm.generate_content(sys_call3a.format(
                    error_message = err_msg,
                    word_problem = op_call2_data.get('word_problem', ''),
                    formula_ids = json.dumps(op_call2_data.get('formula_ids', []), indent=2),
                    variables_dict = json.dumps(op_call2_data.get('variables', {}), indent=2),
                    available_formulas = json.dumps(available_formulas, indent=2)
                ))
            except Exception as e:
                print(f" Call3 retry generation failed: {e}. Skipping this cycle.")
                execution_failures += 1
                continue
            code_text = sanitize_code_text(op_call3a.text if hasattr(op_call3a, 'text') else str(op_call3a))
            action3_result = execute_and_validate_in_repl(code_text, op_call2_data.get('variables', {}))
            print(f" Execution result after retry: {action3_result}")
            if not action3_result.get('valid', False):
                print(" Call3 retry failed. Skipping this cycle.")
                execution_failures += 1
                continue

        # Success: record problem (include numeric result under 'result')
        now = datetime.datetime.utcnow().isoformat()
        successful_record = {
            'signature': signature,
            'formula_ids': op_call2_data.get('formula_ids', []),
            'unknown_var': validation_result.get('unknown_var'),
            'word_problem': op_call2_data.get('word_problem', ''),
            'variables': op_call2_data.get('variables', {}),
            'code': code_text,
            'result': action3_result.get('result'),
            'execution_result': action3_result,
            'validation_result': validation_result,
            'created_at': now
        }
        successful_problems.append(successful_record)
        previous_problems.insert(0, {
            'signature': signature,
            'snippet': op_call2_data.get('word_problem', '')[:140],
            'created_at': now
        })
        previous_problems = previous_problems[:10]
        print(f" Recorded successful problem #{len(successful_problems)}")

    # end two-cycle loop for this iteration

print("\nMulti-problem generation loop completed.")
print(f"Iterations: {current_iteration}, Successful this run: {len(successful_problems)}, Total attempts: {total_cycles_attempted}")
print(f"Duplicates skipped: {duplicates_skipped}, parse_failures: {parse_failures}, execution_failures: {execution_failures}")

# Merge with existing records and write once (atomic)
try:
    existing_signatures = {r.get('signature') for r in existing_records if isinstance(r, dict) and r.get('signature')}
    merged = list(existing_records)
    for rec in successful_problems:
        if rec.get('signature') not in existing_signatures:
            merged.append(rec)
            existing_signatures.add(rec.get('signature'))
    atomic_write_json(success_file_path, merged)
    print(f"Saved merged successful problems to '{success_file_path}' (total {len(merged)})")
except Exception as e:
    print(f"Could not save successful_problems.json: {e}")
