# ProblemGenerationAgent 🚀

![Python](https://img.shields.io/badge/language-Python-blue) ![License](https://img.shields.io/badge/license-MIT-green) ![Status](https://img.shields.io/badge/status-active-success) ![AI](https://img.shields.io/badge/LLM-Gemini-orange)

A multi-agent LLM pipeline that generates diverse physics word problems from seed Q/S pairs, synthesizes solution code, executes numeric checks, and produces an interactive dataset evaluation report.

- Purpose: Automate large-scale generation of structured physics problems with programmatic solution verification and dataset-level quality analytics.
- Approach: Analyze seed Q/S, propose alternate scenarios, generate new word problems, synthesize Python solutions, execute and validate results, and persist validated problems.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Live Evaluation Report](#-live-evaluation-report)
- [Architecture](#-architecture)
- [Installation](#-installation)
- [Usage](#-usage)
- [Output Format](#-output-format)
- [File Structure](#-file-structure)
- [Utilities](#-utilities)
- [Contributing](#-contributing)
- [License & Contact](#-license--contact)

---

> This project would not have been possible without the extensive collaboration of  
> [Sriram Hebbale](https://github.com/sriram-17-17), and the guidance and support of  
> [Prof. Dhruv Kumar](https://github.com/kudhru).

---


## 🎯 Overview

ProblemGenerationAgent orchestrates LLM calls to convert human-authored question/solution pairs into many alternative, machine-checkable physics problems. Each generated problem is paired with synthesized Python solution code that is executed to verify numeric outputs; records are then aggregated and analyzed with a visual HTML report.

Highlights:
- Modular pipeline designed for incremental runs and dataset curation.
- Uses prompt templates + helper utilities to parse, validate, and execute generated artifacts.
- Produces an HTML evaluation report with per-chapter metrics and plots.

---

## ✨ Features

- 🤖 Multi-agent pipeline with retries and structured prompts
- 📚 Formula libraries maintained as structured JSON (chapterwise)
- 🧪 Code synthesis + execution for numeric verification
- 📊 Dataset evaluation producing an interactive HTML report
- 🔧 Utility scripts to filter or collect problems by formula counts
- 📝 Incremental persistence to avoid reprocessing duplicates

---

## 📊 Live Evaluation Report

🔗 View the generated interactive report:
https://er-ads.github.io/ProblemGenerationAgent/Physics_Evaluation_Report.html

Note: Running the local evaluator will produce a single-file HTML report (see `run/dataset_evaluator.py`).

---

## 🏗️ Architecture

User (seed CSV) → Analyze Q&S (Call 1) → Verify formula coverage (Call 1A) → Multi-iteration loop:
- Generate word problem (Call 2)
- Validate problem structure & uniqueness
- Generate Python solution (Call 3)
- Execute & verify numeric result
- Persist validated problems (incremental)

Output: per-CSV generated problems JSON + chapterwise aggregated datasets + HTML evaluation report.

---

## 🚀 Installation

Prerequisites
- Python 3.8+
- (Optional, for generation) Google Generative AI API Key with access to Gemini models

Steps
```bash
git clone https://github.com/er-ads/ProblemGenerationAgent.git
cd ProblemGenerationAgent

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set API key (required for the main generator):
```bash
export GOOGLE_API_KEY='your_api_key_here'
```

Tip: For CI or shared environments, store the key in your secret manager rather than committing it.

---

## 💻 Usage

1) Run the main generator (LLM required)
```bash
cd run
python main_ProblemGeneratorV6.py
```
- The script reads a seed CSV (default filename is set inside the script). It writes incremental output to `<csv-basename>_generated_problems.json` (in the `run/` directory).
- Environment variable: `GOOGLE_API_KEY` is read by the script. The code instantiates `genai.GenerativeModel('gemini-2.5-flash')`.

Callouts:
- NOTE: The default CSV filename is set in the script; you may update it or run a patched/CLI-enabled version to pass a CSV at runtime.
- WARNING: Executing the generation pipeline consumes LLM credits.

2) Generate dataset evaluation report (no LLM calls)
```bash
cd run
python dataset_evaluator.py
```
- Expects chapter JSON files in `chapterwise_generated_dataset/` (wildcard `*.json`).
- Produces `Physics_Evaluation_Report.html` in the repository root (default).

---

## 🔢 Output Format

Each generated problem record follows this general JSON shape (example):
```json
{
  "signature": "fids=[5_A,5_B]|unknown=acceleration",
  "formula_ids": ["5_A", "5_B"],
  "unknown_var": "acceleration",
  "word_problem": "A 2 kg block rests on...",
  "variables": {
    "mass": {"value": 2.0, "unit": "kg"},
    "acceleration": {"value": "NaN", "unit": "m/s^2"}
  },
  "code": "def solve():\n    mass = 2.0\n    ...",
  "result": 4.9,
  "created_at": "2025-01-15T10:30:00Z"
}
```
- "code" stores the synthesized Python solution as text.
- "result" stores the numeric output when code execution succeeded.
- For unknown variables use a clear sentinel (e.g., "NaN" string) as shown above.

Recommendation: Consumers of these JSONs should validate records against a JSON Schema (not included here) or run the dataset evaluator for consistency checks.

---

## 📁 File Structure

Top-level (concise):
```
ProblemGenerationAgent/
├── README.md
├── requirements.txt
├── Physics_Evaluation_Report.html
├── chapterwise_formulas/              # formula libraries (JSON)
├── seed_problems/                     # CSV seed question/solution pairs
├── chapterwise_generated_dataset/     # aggregated generated chapter JSONs
├── run/                               # main scripts and utilities
│   ├── main_ProblemGeneratorV6.py
│   ├── prompts.py
│   ├── pg_helpers.py
│   ├── dataset_evaluator.py
│   ├── defective_problem_filter.py
│   ├── N_formula_collector.py
│   └── two_formula_collector.py
└── ...
```
- The `run/` directory contains the main orchestrator, prompt templates, helper utilities, and dataset tools.

---

## 🛠️ Utilities

- run/defective_problem_filter.py
  - Removes problems with ≤1 formulas and consolidates them into `global_defective_problems.json`.

- run/N_formula_collector.py / run/two_formula_collector.py
  - Collects problems with exactly N formulas into `global_{N}_formula_count.json`.

- run/dataset_evaluator.py
  - Produces a self-contained HTML report embedding plots (base64 PNGs) and per-chapter metrics.

---

## 🤝 Contributing

Contributions are welcome. Suggested workflow:
1. Fork the repository
2. Create a feature branch: git checkout -b feature/awesome
3. Add tests for logic changes (especially helpers and validators)
4. Commit and push, then open a PR

Helpful additions:
- CLI/argparse support for main_ProblemGeneratorV6.py
- JSON Schema for produced problem objects
- Unit tests for pg_helpers (signature, parser, execution checks)
- CI workflow to run dataset_evaluator and basic linters

---

## 📄 License & Contact

This project is licensed under the MIT License — see the LICENSE file.

Project Maintainer: er-ads — open issues or PRs at:
https://github.com/er-ads/ProblemGenerationAgent/issues

---

<div align="center">
**⭐ Star this repository if you find it useful!**
</div>
