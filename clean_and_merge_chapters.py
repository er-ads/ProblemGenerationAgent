#!/usr/bin/env python3

"""
Clean and merge chapterwise physics JSON files into a single JSONL dataset.
"""

import os, glob, json, math, re
from typing import Any

# ============================================================
# HARD-CODED PATHS (AUTO-DETECTED NOW)
# ============================================================
# This fixes the "No files found" error by looking relative to the script's location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(SCRIPT_DIR, "chapterwise_generated_dataset")
OUTPUT_JSONL = os.path.join(SCRIPT_DIR, "final_dataset.jsonl")


# ============================================================
# FINAL SCHEMA
# ============================================================
FINAL_KEYS = [
    "chapter",
    "word_problem",
    "execution_result",
    "signature",
    "formula_ids",
    "unknown_var",
    "variables",
    "code",
    "validation_result",
]


# ============================================================
# EXTRACT CHAPTER NAME FROM FILENAME
# ============================================================
def extract_chapter_from_filename(path: str) -> str:
    name = os.path.splitext(os.path.basename(path))[0]
    name_after = re.sub(r'^[0-9]+(?:[-_][0-9]+)?\.\s*', "", name)
    return name_after.replace("_", " ").strip() or name


# ============================================================
# CLEAN VALUE (Fix NaN/Inf)
# ============================================================
def clean_value(v: Any) -> Any:
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    if isinstance(v, dict):
        return {k: clean_value(val) for k, val in v.items()}
    if isinstance(v, list):
        return [clean_value(x) for x in v]
    if isinstance(v, str):
        if v.lower() in ("nan", "inf", "-inf", "+inf", "none", "null", "na"):
            return None
        return v
    return v


# ============================================================
# NORMALIZE STRUCTURE TO FINAL SCHEMA
# ============================================================
def normalize_record(raw: dict, chapter: str) -> dict:
    """Return a cleaned and schema-aligned record."""
    cleaned = clean_value(raw if isinstance(raw, dict) else {})

    out = {key: None for key in FINAL_KEYS}
    out["chapter"] = chapter

    # Copy fields we allow
    for key in FINAL_KEYS:
        if key == "chapter":
            continue
        
        if key in cleaned:
            val = cleaned[key]
            
            # --- MODIFICATION: Extract simple result from execution_result dict ---
            if key == "execution_result" and isinstance(val, dict) and "result" in val:
                # Changes {"valid": true, "result": 84} -> "84" (or 84)
                # We convert to str() to ensure it matches your requested format "84"
                out[key] = str(val["result"]) 
            else:
                out[key] = val

    # Enforce basic types
    if out["formula_ids"] is None:
        out["formula_ids"] = []
    if out["variables"] is None:
        out["variables"] = {}

    return out


# ============================================================
# LOAD MULTI-OBJECT JSON FILES
# ============================================================
def load_json_multi(path: str):
    print(f"\n[DEBUG] Loading file: {path}")

    with open(path, "r", encoding="utf-8") as f:
        text = f.read().strip()

    if not text:
        return []

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except:
        pass

    objects = []
    buffer = ""
    brace_count = 0

    for char in text:
        buffer += char
        if char == "{":
            brace_count += 1
        elif char == "}":
            brace_count -= 1

        if brace_count == 0 and buffer.strip():
            try:
                obj = json.loads(buffer)
                objects.append(obj)
            except Exception as e:
                print(f"[WARNING] Failed block: {e}")
            buffer = ""

    return objects


# ============================================================
# MAIN MERGE LOGIC
# ============================================================
def main():
    print("\n========================================")
    print("Scanning folder:", INPUT_DIR)
    print("========================================\n")

    # Check if directory exists
    if not os.path.exists(INPUT_DIR):
        print(f"❗ ERROR: Directory not found: {INPUT_DIR}")
        print(f"  Current working dir: {os.getcwd()}")
        return

    paths = sorted(
        glob.glob(os.path.join(INPUT_DIR, "*.json")) +
        glob.glob(os.path.join(INPUT_DIR, "*.jsonl"))
    )

    if not paths:
        print("\n❗ No files found. Check INPUT_DIR.\n")
        return

    merged = []

    for p in paths:
        chapter = extract_chapter_from_filename(p)
        print(f"Processing: {os.path.basename(p)} -> Chapter: '{chapter}'")

        records = load_json_multi(p)
        for rec in records:
            merged.append(normalize_record(rec, chapter))

    print("\n========================================")
    print("TOTAL MERGED RECORDS =", len(merged))
    print("========================================\n")

    with open(OUTPUT_JSONL, "w", encoding="utf-8") as fout:
        for item in merged:
            fout.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"✔ Done. Wrote to {OUTPUT_JSONL}")


if __name__ == "__main__":
    main()