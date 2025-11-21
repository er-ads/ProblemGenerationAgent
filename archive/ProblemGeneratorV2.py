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


def validate_problem(output, formula_dict, variable_ranges, previous_problems):
    # Check 1: All formula_ids exist
    if not all(fid in formula_dict for fid in output["formula_ids"]):
        return {"valid": False, "error": "Invalid formula_id"}
    
    # Check 2: Exactly one NaN variable
    nan_vars = [k for k, v in output["variables"].items() if v["value"] == "NaN"]
    if len(nan_vars) != 1:
        return {"valid": False, "error": f"Must have exactly 1 unknown, found {len(nan_vars)}"}
    
    unknown_var = nan_vars[0]
    
    # Check 3: Values within specified ranges
    for var_name, var_data in output["variables"].items():
        if var_data["value"] != "NaN":
            if var_name in variable_ranges:
                range_min, range_max = variable_ranges[var_name]["range"]
                
                # Explicitly convert to float for reliable numerical comparison
                try:
                    actual_value = float(var_data["value"])
                except (ValueError, TypeError):
                    # Handle cases where value is not "NaN" but also not a valid number
                    return {"valid": False, "error": f"Variable '{var_name}' has an invalid numerical value: '{var_data['value']}'."}

                if not (range_min <= actual_value <= range_max):
                    return {"valid": False, "error": f"{var_name} with value {actual_value} is out of expected range [{range_min}, {range_max}]."}
        
    # # Check 4: Uniqueness - compare (formula_ids set, unknown_var) tuple
    # current_signature = (frozenset(output["formula_ids"]), unknown_var)
    # for prev_problem in previous_problems:
    #     prev_signature = (frozenset(prev_problem["formula_ids"]), prev_problem["unknown_var"])
    #     if current_signature == prev_signature:
    #         return {"valid": False, "error": "Duplicate problem signature"}
    
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

# [[[LLM CALL 2]]] # Word Problem Generation

op_call2 = llm.generate_content(sys_call2.format(
    available_formulas = json.dumps(available_formulas, indent=2),
    alternate_scenarios = json.dumps(op_call1_data['alternate_scenarios'], indent=2),
    variables = json.dumps(op_call1_data['variables'], indent=2),
    previous_problems = "..."
    # previous_problems = json.dumps(op_call1_data['previous_problems'], indent=2)
))

print(op_call2.text)
op_call2_data = llm_op_to_json(op_call2)

# [[[ACTION 2]]] # Programmatic Check for Word Problem Validity \

#generating formula_ids for validation

formula_list = []
for formula in available_formulas.values():
    for item in formula:
        formula_list.append(item['formula_id'])

validation_result = validate_problem(
    output=op_call2_data,
    formula_dict=formula_list,
    variable_ranges=op_call1_data['variables'],
    previous_problems = "..."
    # previous_problems=op_call1_data['previous_problems']
)

print(f"Validation Result: {validation_result}")


print("Call 2 Completed---------------------------------------------------------------------------- \n ")

#################################################################################################################

# [[[LLM CALL 2A]]] # Word Problem Generation in Case of Error 

# If `valid == False`, retry Call 2 once with error message added to prompt. If fails twice, skip this iteration and continue loop.

if not validation_result["valid"]:
    error_message = validation_result["error"]
    print(f"Validation failed: {error_message}. Retrying LLM Call 2 with error message.")

    op_call2a = llm.generate_content(sys_call2a.format(
        error_message = error_message,
        available_formulas = json.dumps(available_formulas, indent=2),
        alternate_scenarios = json.dumps(op_call1_data['alternate_scenarios'], indent=2),
        variables = json.dumps(op_call1_data['variables'], indent=2),
        previous_problems = "..."
        # previous_problems = json.dumps(op_call1_data['previous_problems'], indent=2)
    ))

    print(op_call2a.text)
    op_call2a_data = llm_op_to_json(op_call2a)

    # Re-validate after retry
    validation_result = validate_problem(
        output=op_call2a_data,
        formula_dict=available_formulas,
        variable_ranges=op_call1_data['variables'],
        # previous_problems=op_call1_data['previous_problems']
    )

    if not validation_result["valid"]:
        print(f"Retry also failed: {validation_result['error']}. Skipping this iteration.")  
        sys.exit()  # Exit or continue as per your requirement

#################################################################################################################

# [[[LLM CALL 3]]] # Python Code Generation 

op_call3 = llm.generate_content(sys_call3.format(
    word_problem = op_call2_data['word_problem'],
    formula_ids = json.dumps(op_call2_data['formula_ids'], indent=2),
    variables_dict = json.dumps(op_call2_data['variables'], indent=2),  
    available_formulas = json.dumps(available_formulas, indent=2)
    # available_formulas = formulas_json
))

print(op_call3.text)

# [[[ACTION 3]]] # Execute and Validate Code using REPL

action3_result = execute_and_validate_in_repl(op_call3.text,op_call2_data['variables'])
print(f"Execution and Validation Result: {action3_result}")

print("Call 3 Completed---------------------------------------------------------------------------- \n ")

#################################################################################################################

# [[[LLM CALL 3A]]] # Python Code Generation in Case of Error

if not action3_result["valid"]:
    op_call3a = llm.generate_content(sys_call3a.format(
        error_message = action3_result["error"],
        word_problem = op_call2_data['word_problem'],
        formula_ids = json.dumps(op_call2_data['formula_ids'], indent=2),
        variables_dict = json.dumps(op_call2_data['variables'], indent=2),  
        available_formulas = json.dumps(available_formulas, indent=2)
        # available_formulas = formulas_json
    ))

    print(op_call3a.text)
    # Re-execute and re-validate after retry
    action3_result = execute_and_validate_in_repl(op_call3a.text,op_call2_data['variables'])
    print(f"Retry Execution and Validation Result: {action3_result}")

#################################################################################################################