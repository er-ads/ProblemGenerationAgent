import os
import json
import math
import traceback


def inner_load_json_from_file(filename):
    """
    Load a JSON file and return its contents as a pretty JSON string.
    This is useful for passing structured data into LLM prompts.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(current_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return json.dumps(data, indent=2)


def load_json_from_file(filename):
    """
    Safe wrapper around `inner_load_json_from_file` that prints helpful errors.
    Returns a pretty JSON string or None on error.
    """
    try:
        return inner_load_json_from_file(filename)
    except FileNotFoundError as e:
        print(f"Error loading JSON file: {e}")
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from file: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def llm_op_to_json(op_call):
    """
    Clean an LLM text response and parse it as JSON.
    The LLM may include fences like ```json or ```; this strips them and attempts to load JSON.
    Returns a Python object on success, or None on failure.
    """
    if not hasattr(op_call, 'text'):
        s = str(op_call)
    else:
        s = op_call.text
    cleaned = s.strip()
    if cleaned.startswith('```json'):
        cleaned = cleaned[len('```json'):].strip()
    if cleaned.endswith('```'):
        cleaned = cleaned[:-len('```')].strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        print("=========================================================================")
        print(f"Error after cleaning: JSONDecodeError: {e}")
        print("Problematic string start:")
        print(f"{cleaned[:500]}...")
    except Exception as e:
        print("=========================================================================")
        print(f"Unexpected error parsing LLM output: {e}")
        traceback.print_exc()
    return None


def normalize_available_formula_ids(available_formulas):
    """
    Given the `available_formulas` structure (often a dict of lists or nested dicts),
    return a tuple `(set_of_ids, map_id_to_formula)`.
    This makes it easy to validate `formula_ids` returned by the LLM.
    """
    ids = set()
    by_id = {}
    if not isinstance(available_formulas, dict):
        return ids, by_id
    for key, val in available_formulas.items():
        if isinstance(val, dict):
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
    return ids, by_id


def compute_problem_signature(op_call2_data):
    """
    Compute a canonical signature for a generated problem.
    The signature uses the sorted `formula_ids` plus the unknown variable name.
    This helps detect duplicates across runs.
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
    return sig


def format_previous_problems_for_prompt(previous_problems, max_items=5):
    """
    Create a compact JSON string listing recent problem signatures and short snippets.
    This can be passed to the LLM so it avoids generating duplicates.
    """
    compact = []
    for p in previous_problems[:max_items]:
        compact.append({
            'signature': p.get('signature'),
            'snippet': p.get('snippet', '')[:140]
        })
    return json.dumps(compact, indent=2)


def sanitize_code_text(code_text):
    """
    Extract Python code from an LLM response.
    If the response contains fenced blocks (```), prefer a fenced block that looks like Python.
    Otherwise return the trimmed text.
    """
    if not isinstance(code_text, str):
        return code_text
    s = code_text.strip()
    if '```' in s:
        parts = s.split('```')
        for part in parts:
            part_strip = part.strip()
            if not part_strip:
                continue
            if part_strip.startswith('def ') or part_strip.startswith('import') or 'def solve' in part_strip:
                return part_strip
        if len(parts) >= 2:
            return parts[1].strip()
    return s


def validate_problem(output, formula_dict, variable_ranges, previous_problems):
    """
    Basic checks on the LLM-generated problem structure:
    - all formula_ids are present in available formulas
    - exactly one unknown (NaN) variable
    - numeric values fall within provided ranges (if available)
    - signature uniqueness vs `previous_problems`

    Returns a dict: `{'valid': bool, 'error': msg_if_any, 'unknown_var': name_if_valid}`
    """
    if isinstance(formula_dict, dict):
        formula_id_set = set(formula_dict.keys())
    else:
        try:
            formula_id_set = set(formula_dict)
        except Exception:
            formula_id_set = set()

    if not all(fid in formula_id_set for fid in output.get('formula_ids', [])):
        return {'valid': False, 'error': 'Invalid formula_id'}

    nan_vars = [k for k, v in output.get('variables', {}).items() if str(v.get('value')).lower() == 'nan']
    if len(nan_vars) != 1:
        return {'valid': False, 'error': f'Must have exactly 1 unknown, found {len(nan_vars)}'}

    unknown_var = nan_vars[0]

    for var_name, var_data in output.get('variables', {}).items():
        if str(var_data.get('value')).lower() != 'nan':
            if var_name in variable_ranges:
                rr = variable_ranges[var_name].get('range') if isinstance(variable_ranges[var_name], dict) else None
                if rr and isinstance(rr, (list, tuple)) and len(rr) == 2:
                    range_min, range_max = rr
                    try:
                        actual_value = float(var_data.get('value'))
                    except (ValueError, TypeError):
                        return {'valid': False, 'error': f"Variable '{var_name}' has an invalid numerical value: '{var_data.get('value')}'."}
                    if not (range_min <= actual_value <= range_max):
                        return {'valid': False, 'error': f"{var_name} with value {actual_value} is out of expected range [{range_min}, {range_max}]."}

    try:
        current_signature = compute_problem_signature(output)
        for prev_problem in previous_problems:
            if prev_problem.get('signature') == current_signature:
                return {'valid': False, 'error': 'Duplicate problem signature'}
    except Exception:
        pass

    return {'valid': True, 'unknown_var': unknown_var}


def execute_and_validate_in_repl(code, variables):
    """
    Execute the provided code in an isolated namespace and call `solve()`.
    Perform simple checks on the returned value (numeric, not NaN/Inf, basic sign sanity).
    Returns dict: `{'valid': bool, 'result': number_or_None, 'error': msg_if_any}`
    """
    repl_globals = {}
    try:
        exec(code, repl_globals)
        if 'solve' not in repl_globals or not callable(repl_globals['solve']):
            return {'valid': False, 'error': "'solve()' function not found", 'result': None}
        result = repl_globals['solve']()
    except Exception as e:
        return {'valid': False, 'error': f'Execution failed: {str(e)}', 'result': None}

    if result is None or not isinstance(result, (int, float)):
        return {'valid': False, 'error': 'Invalid return type', 'result': None}
    if math.isnan(result) or math.isinf(result):
        return {'valid': False, 'error': 'Result is NaN or Inf', 'result': None}

    unknown_vars = [k for k, v in variables.items() if str(v.get('value')).lower() == 'nan']
    if unknown_vars:
        unknown_var = unknown_vars[0]
        if result < 0 and any(x in unknown_var.lower() for x in ['mass', 'distance', 'time', 'speed', 'velocity', 'energy']):
            return {'valid': False, 'error': f'Negative value for {unknown_var}', 'result': result}

    return {'valid': True, 'result': result}


def atomic_write_json(path, data):
    """
    Write `data` (a Python object) to `path` atomically using a .tmp file and os.replace.
    """
    tmp_path = path + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, path)


def iterate_csv_pairs(csv_filename, required_columns=('question', 'solution'), encoding='utf-8', start_index=1):
    """
    Generator that yields rows from a CSV file as dictionaries with normalized (lowercase) keys.

    Resolution logic for `csv_filename`:
    - if `csv_filename` is absolute, use it
    - else try the path as given relative to this file's directory
    - else try ../seed_problems/<csv_filename> relative to this file's directory

    Each yielded dict will contain at minimum the keys `question` and `solution` (trimmed strings),
    and two derived fields if not provided: `Pair_Number` (int) and `source_problem_ID` (str).

    Rows missing required fields are skipped with a printed warning.
    """
    import csv

    current_dir = os.path.dirname(os.path.abspath(__file__))

    candidates = []
    if os.path.isabs(csv_filename):
        candidates.append(csv_filename)
    else:
        candidates.append(os.path.join(current_dir, csv_filename))
        candidates.append(os.path.join(current_dir, '..', 'seed_problems', csv_filename))
        candidates.append(os.path.join(current_dir, '..', csv_filename))

    csv_path = None
    for c in candidates:
        if os.path.exists(c):
            csv_path = c
            break

    if not csv_path:
        raise FileNotFoundError(f"CSV file not found. Tried: {candidates}")

    pair_counter = start_index
    with open(csv_path, 'r', encoding=encoding, newline='') as fh:
        reader = csv.DictReader(fh)
        # normalize fieldnames to lowercase
        if reader.fieldnames:
            normalized_fieldnames = [fn.strip().lower() for fn in reader.fieldnames]
            mapping = {orig: norm for orig, norm in zip(reader.fieldnames, normalized_fieldnames)}
        else:
            mapping = {}

        for raw_row in reader:
            # normalize keys
            row = { (k.strip().lower() if k is not None else k): (v.strip() if isinstance(v, str) else v) for k, v in raw_row.items() }

            # validate required columns
            missing = [c for c in required_columns if not row.get(c)]
            if missing:
                print(f"Skipping CSV row {pair_counter}: missing required columns: {missing}")
                pair_counter += 1
                continue

            # ensure Pair_Number
            try:
                if row.get('pair_number'):
                    pn = int(row.get('pair_number'))
                else:
                    pn = pair_counter
            except Exception:
                pn = pair_counter

            row['Pair_Number'] = pn

            # ensure source_problem_ID
            if not row.get('source_problem_id'):
                chapter = row.get('chapter_name') or row.get('chapter') or ''
                if chapter:
                    row['source_problem_ID'] = f"{chapter}_R{pn}"
                else:
                    row['source_problem_ID'] = f"CSV_R{pn}"
            else:
                row['source_problem_ID'] = row.get('source_problem_id')

            yield row
            pair_counter += 1
