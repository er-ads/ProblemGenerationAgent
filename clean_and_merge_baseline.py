#!/usr/bin/env python3
"""
Clean and merge baseline generated problem files into a single JSONL dataset.

Output (option B): chapterwise_generated_dataset/merged_baseline_cleaned.jsonl

This script produces records with EXACT keys and order:
  ["chapter", "word_problem", "execution_result", "signature", "source_problemID", "pair_number"]

It builds a canonical chapter table from `chapterwise_generated_dataset` and maps
baseline `source_problem_ID` values to those chapter names.
"""

import os
import glob
import json
import math
import re
import difflib
import time
from typing import Any, Dict, List, Tuple


# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASELINE_DIR = os.path.join(SCRIPT_DIR, "ProblemGeneratorBaselineDB")
CHAPTER_DIR = os.path.join(SCRIPT_DIR, "chapterwise_generated_dataset")
OUTPUT_JSONL = os.path.join(CHAPTER_DIR, "merged_baseline_cleaned.jsonl")
MAPPING_CACHE = os.path.join(SCRIPT_DIR, "baseline_chapter_mapping_cache.json")


# Debug verbosity (can set env BASELINE_MERGE_VERBOSE=0 to quiet)
VERBOSE = os.environ.get("BASELINE_MERGE_VERBOSE", "1") not in ("0", "false", "False")

# Final ordered keys required by the user
FINAL_KEYS = ["chapter", "word_problem", "execution_result", "signature", "source_problemID", "pair_number"]


def extract_chapter_from_filename(path: str) -> str:
    name = os.path.splitext(os.path.basename(path))[0]
    name_after = re.sub(r'^[0-9]+(?:[-_][0-9]+)?\.?\s*', "", name)
    return name_after.replace("_", " ").strip() or name


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
        s = v.strip()
        if s == "":
            return None
        if s.lower() in ("nan", "inf", "-inf", "+inf", "none", "null", "na"):
            return None
        return s
    return v


def load_json_multi(path: str) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read().strip()

    if not text:
        return []

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except Exception:
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
            except Exception:
                # skip malformed block but continue
                pass
            buffer = ""

    return objects


def normalize_key_names(raw: Dict) -> Dict:
    # Map common baseline keys to normalized names
    out = {}
    for k, v in (raw or {}).items():
        lk = k.lower()
        if lk in ("signature",):
            out["signature"] = v
        elif lk in ("source_problem_id", "source_problemid", "source_problem-id"):
            out["source_problemID"] = v
        elif lk in ("pair_number", "pairnumber", "pair-number") or k in ("Pair_Number",):
            out["pair_number"] = v
        elif lk in ("problem_text", "problemtext", "word_problem"):
            out["word_problem"] = v
        elif lk in ("numerical_answer", "numericalanswer", "execution_result", "result"):
            out["execution_result"] = v
        else:
            # keep original key under its original name in out for potential metadata
            out[k] = v

    return out


def normalize_text_key(s: str) -> str:
    if s is None:
        return ""
    s = str(s)
    s = s.replace("_", " ")
    s = s.replace("&", "and")
    s = s.replace("\"", "")
    s = re.sub(r"[^0-9a-zA-Z\s]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


def build_canonical_chapter_table(chapter_dir: str) -> Tuple[Dict[str, str], List[Tuple[str, str]]]:
    table = {}
    entries = []
    patterns = []
    paths = sorted(glob.glob(os.path.join(chapter_dir, "*.json")))
    for p in paths:
        name = extract_chapter_from_filename(p)
        norm = normalize_text_key(name)
        table[norm] = name
        entries.append((norm, name))
        # also store the numeric prefix for numeric-range matching
        base = os.path.basename(p)
        m = re.match(r'^([0-9]+(?:[-_][0-9]+)?)\.', base)
        if m:
            patterns.append((m.group(1), name))

    return table, patterns


def match_chapter(candidate: str, canonical_table: Dict[str, str], numeric_patterns: List[Tuple[str, str]]) -> Tuple[str, float]:
    # Returns (chapter_name, score) or (None, 0)
    cand_norm = normalize_text_key(candidate)
    if not cand_norm:
        return None, 0.0

    # exact
    if cand_norm in canonical_table:
        return canonical_table[cand_norm], 1.0

    # token overlap
    cand_tokens = set(cand_norm.split())
    best = (None, 0.0)
    for norm, name in canonical_table.items():
        tokens = set(norm.split())
        if not tokens:
            continue
        overlap = len(cand_tokens & tokens) / max(1, len(tokens))
        if overlap > best[1]:
            best = (name, overlap)
    if best[1] >= 0.6:
        return best[0], best[1]

    # fuzzy match
    for norm, name in canonical_table.items():
        r = difflib.SequenceMatcher(None, cand_norm, norm).ratio()
        if r > best[1]:
            best = (name, r)
    if best[1] >= 0.75:
        return best

    # numeric-range fallback: look for trailing R<number> or digits inside
    m = re.search(r'\bR?(\d{1,3})\b', candidate)
    if m:
        num = int(m.group(1))
        # try to match numeric_patterns (like '2-4' or '10')
        for pat, name in numeric_patterns:
            if '-' in pat:
                a, b = pat.split('-', 1)
                try:
                    if int(a) <= num <= int(b):
                        return name, 0.5
                except Exception:
                    continue
            else:
                try:
                    if int(pat) == num:
                        return name, 0.5
                except Exception:
                    continue

    return None, 0.0


def normalize_record_to_final(raw: Dict, canonical_table: Dict[str, str], numeric_patterns: List[Tuple[str, str]], mapping_cache: Dict[str, str], diagnostics: List[Dict]) -> Dict:
    # Normalize keys and clean values
    normalized = normalize_key_names(clean_value(raw))

    # Prepare final record with exact keys in exact order
    out = {k: None for k in FINAL_KEYS}

    # word_problem
    out["word_problem"] = normalized.get("word_problem") if normalized.get("word_problem") is not None else normalized.get("problem_text")

    # signature
    out["signature"] = normalized.get("signature")

    # source_problemID
    src = normalized.get("source_problemID") or normalized.get("source_problem_ID") or normalized.get("source_problemid")
    if src is None:
        # try derive from signature
        sig = out["signature"]
        if sig and isinstance(sig, str):
            parts = sig.split('_')
            if len(parts) >= 2:
                src = '_'.join(parts[:2])

    out["source_problemID"] = src

    # pair_number
    pn = normalized.get("pair_number")
    if pn is None:
        pn = raw.get("variation_number") if isinstance(raw, dict) else None
    try:
        if pn is None:
            out["pair_number"] = None
        else:
            out["pair_number"] = int(pn)
    except Exception:
        out["pair_number"] = None
        diagnostics.append({"issue": "pair_number_coercion", "value": pn, "record": raw})

    # execution_result: ensure string if present
    er = normalized.get("execution_result")
    if isinstance(er, dict) and "result" in er:
        er = er["result"]
    if er is None:
        if "numerical_answer" in raw:
            er = raw.get("numerical_answer")
    if er is not None:
        if isinstance(er, (int, float)):
            out["execution_result"] = str(er)
        else:
            out["execution_result"] = str(er)
    else:
        out["execution_result"] = None

    # chapter extraction & mapping (with verbose debugging)
    chapter = None
    cache_key = str(out.get("source_problemID") or "")
    if VERBOSE:
        print("  [DBG] cache_key=", cache_key)

    if cache_key and cache_key in mapping_cache:
        chapter = mapping_cache[cache_key]
        if VERBOSE:
            print(f"  [DBG] found in mapping_cache -> {chapter}")
    else:
        cand = cache_key
        if not cand:
            cand = out.get("signature") or ""
            if cand and '_' in cand:
                cand = cand.rsplit('_', 2)[0]
        cand_raw = cand
        cand = re.sub(r'_R\d+$', '', cand)
        cand = cand.replace('_', ' ')
        if VERBOSE:
            print(f"  [DBG] candidate for matching: '{cand_raw}' -> normalized '{cand}'")

        matched, score = match_chapter(cand, canonical_table, numeric_patterns)
        if matched:
            chapter = matched
            if cache_key:
                mapping_cache[cache_key] = chapter
            if VERBOSE:
                print(f"  [DBG] matched by candidate -> '{chapter}' (score={score:.3f})")
        else:
            if '_' in cand:
                cand2 = cand.split('_')[0]
                matched2, score2 = match_chapter(cand2, canonical_table, numeric_patterns)
                if matched2:
                    chapter = matched2
                    if cache_key:
                        mapping_cache[cache_key] = chapter
                    if VERBOSE:
                        print(f"  [DBG] matched by cand2 -> '{chapter}' (score={score2:.3f})")

    if not chapter:
        chapter = "Unknown"
        diagnostics.append({"issue": "chapter_unmapped", "source_problemID": cache_key, "record_signature": out.get("signature")})
        if VERBOSE:
            print(f"  [DBG] chapter unmapped for source_problemID='{cache_key}' -> set 'Unknown'")

    out["chapter"] = chapter

    return out


def main():
    print("Scanning baseline directory:", BASELINE_DIR)
    if not os.path.exists(BASELINE_DIR):
        print("ERROR: baseline directory not found:", BASELINE_DIR)
        return

    canonical_table, numeric_patterns = build_canonical_chapter_table(CHAPTER_DIR)

    mapping_cache = {}
    try:
        if os.path.exists(MAPPING_CACHE):
            with open(MAPPING_CACHE, "r", encoding="utf-8") as mc:
                mapping_cache = json.load(mc)
    except Exception:
        mapping_cache = {}

    raw_paths = glob.glob(os.path.join(BASELINE_DIR, "*_generated_problems.json")) + glob.glob(os.path.join(BASELINE_DIR, "*.json"))
    # dedupe while preserving order
    seen = set()
    paths = []
    for p in raw_paths:
        if p not in seen:
            seen.add(p)
            paths.append(p)

    if VERBOSE:
        print(f"Found {len(paths)} baseline JSON files:")
        for p in paths:
            print(" ", os.path.basename(p))
    merged = []
    diagnostics = []

    file_counts = {}
    for p in paths:
        name = os.path.basename(p)
        print("Processing baseline file:", name)
        try:
            records = load_json_multi(p)
        except Exception as e:
            print("Failed to load", p, e)
            continue
        file_counts[name] = len(records)
        if VERBOSE:
            print(f"  [DBG] loaded {len(records)} records from {name}")
            if len(records) > 0:
                first_keys = list(records[0].keys())
                print(f"  [DBG] first record keys: {first_keys}")

        for idx, rec in enumerate(records, start=1):
            try:
                if VERBOSE:
                    sig_preview = rec.get('signature') if isinstance(rec, dict) else None
                    spid_preview = rec.get('source_problem_ID') if isinstance(rec, dict) else None
                    print(f"  [DBG] record #{idx}: signature='{sig_preview}' source_problem_ID='{spid_preview}'")
                final = normalize_record_to_final(rec, canonical_table, numeric_patterns, mapping_cache, diagnostics)
                # If chapter remained Unknown but this file is a kinematics file, force to 'Kinematics'
                if final.get('chapter') == 'Unknown' and 'kinemat' in name.lower():
                    final['chapter'] = 'Kinematics'
                    # persist mapping for this source_problemID if available
                    spid = final.get('source_problemID')
                    if spid:
                        mapping_cache[str(spid)] = 'Kinematics'
                    if VERBOSE:
                        print(f"  [DBG] Overrode chapter to 'Kinematics' for record from file {name} (source_problemID={spid})")

                merged.append(final)
                if VERBOSE:
                    print(f"  [DBG] -> mapped chapter='{final.get('chapter')}' source_problemID='{final.get('source_problemID')}' pair_number={final.get('pair_number')}")
            except Exception as e:
                diagnostics.append({"issue": "record_normalization_error", "error": str(e), "record": rec})
                if VERBOSE:
                    print(f"  [ERROR] normalization failed for record #{idx}: {e}")

    os.makedirs(CHAPTER_DIR, exist_ok=True)
    with open(OUTPUT_JSONL, "w", encoding="utf-8") as fout:
        for item in merged:
            fout.write(json.dumps(item, ensure_ascii=False) + "\n")

    try:
        with open(MAPPING_CACHE, "w", encoding="utf-8") as mc:
            json.dump(mapping_cache, mc, ensure_ascii=False, indent=2)
        if VERBOSE:
            print(f"Saved mapping cache to {MAPPING_CACHE} (entries={len(mapping_cache)})")
    except Exception as e:
        if VERBOSE:
            print(f"Failed to save mapping cache: {e}")

    try:
        if diagnostics:
            with open(os.path.join(SCRIPT_DIR, "baseline_merge_diagnostics.json"), "w", encoding="utf-8") as df:
                json.dump(diagnostics, df, ensure_ascii=False, indent=2)
    except Exception:
        pass

    print("TOTAL MERGED RECORDS =", len(merged))
    # show counts per source file
    if VERBOSE:
        print("Per-file record counts:")
        for k, v in file_counts.items():
            print(f"  {k}: {v}")
        # show top 10 chapters found
        from collections import Counter
        ch_counts = Counter([x.get('chapter') for x in merged])
        print("Top chapter counts:")
        for ch, cnt in ch_counts.most_common(20):
            print(f"  {ch}: {cnt}")

    print("Wrote:", OUTPUT_JSONL)


if __name__ == '__main__':
    main()
