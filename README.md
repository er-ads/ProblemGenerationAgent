# ProblemGenerationAgent 🚀

![Python](https://img.shields.io/badge/language-Python-blue) ![License](https://img.shields.io/badge/license-MIT-green) ![Status](https://img.shields.io/badge/status-active-success) ![AI](https://img.shields.io/badge/powered%20by-Gemini%202.5-purple)

> **A multi-agent LLM system for automated generation of high-quality physics problems with verified solutions**

This project demonstrates how large language models can be orchestrated to create diverse, validated physics problems across multiple difficulty levels—complete with step-by-step solutions and executable Python code.

---

## 📊 Live Evaluation Report

🔗 **[View Comprehensive Dataset Analysis](https://er-ads.github.io/ProblemGenerationAgent/Physics_Evaluation_Report.html)**

Explore interactive visualizations, quality metrics, and chapter-wise breakdowns of the generated problem dataset.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Usage](#usage)
- [File Structure](#file-structure)
- [Dataset Evaluation](#dataset-evaluation)
- [Utilities](#utilities)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)

---

## 🎯 Overview

**ProblemGenerationAgent** automates the creation of physics problems by:

1. **Analyzing** seed problems to extract concepts and formulas
2. **Generating** diverse alternate scenarios using LLMs
3. **Validating** problems for correctness and uniqueness
4. **Synthesizing** Python code to verify numerical solutions
5. **Persisting** validated problems with comprehensive metadata

The system covers 9 physics chapters from **Rectilinear Motion** to **Rigid Body Dynamics**, producing problems at JEE Mains+ difficulty level.

---

## ✨ Key Features

- 🤖 **Multi-Agent Pipeline**: Orchestrated LLM calls with error handling and retry logic
- 📐 **Formula-Driven Generation**: Uses 100+ physics formulas from structured JSON libraries
- ✅ **Automated Validation**: Checks for logical consistency, uniqueness, and numerical correctness
- 🔢 **Code Synthesis & Execution**: Generates and executes Python solutions for each problem
- 📊 **Quality Metrics**: Built-in evaluation tools for diversity, difficulty, and balance
- 🎨 **Rich Visualizations**: HTML reports with interactive chapter-wise analysis
- 🔧 **Utility Scripts**: Filter, collect, and analyze problems by formula count or other criteria

---

## 🏗️ Architecture
```
User → Seed Problem (CSV) 
       ↓
[Call 1: Analyze Q&S] → Extract chapters, variables, scenarios
       ↓
[Call 1A: Verify Formulas] → Ensure formula completeness
       ↓
[Multi-Iteration Loop]
   ├─ [Call 2: Generate Word Problem] → Create problem statement
   ├─ [Validation] → Check formula IDs, uniqueness, ranges
   ├─ [Call 3: Generate Python Code] → Synthesize solution code
   ├─ [Execution] → Validate numerical result
   └─ [Persist] → Save to JSON (incremental)
       ↓
Output → chapter_generated_problems.json
```

**Key Components:**
- `main_ProblemGeneratorV6.py`: Main orchestrator
- `prompts.py`: LLM prompt templates
- `pg_helpers.py`: Validation, execution, and utility functions
- `chapterwise_formulas/`: Physics formula library (JSON)
- `seed_problems/`: Input CSV files with example problems

---

## 🚀 Installation

### Prerequisites
- Python 3.8+
- Google Generative AI API Key (Gemini 2.5 Flash)

### Steps
```bash
# Clone the repository
git clone https://github.com/er-ads/ProblemGenerationAgent.git
cd ProblemGenerationAgent

# Install dependencies
pip install -r requirements.txt

# Set up API key
export GOOGLE_API_KEY='your_api_key_here'
```

---

## 💻 Usage

### Basic Problem Generation
```bash
cd run
python main_ProblemGeneratorV6.py
```

By default, this processes `5.Newton's Laws of Motion.csv` and outputs to `5.Newton's Laws of Motion_generated_problems.json`.

**To process a different chapter:**
```python
# Edit main_ProblemGeneratorV6.py (line 36)
csv_filename = "8.Circular Motion.csv"
```

### Output Format

Each generated problem includes:
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

---

## 📁 File Structure
```
ProblemGenerationAgent/
├── README.md                          # This file
├── requirements.txt                   # Python dependencies
├── chapterwise_formulas/              # Physics formula library
│   ├── chapter_manifest.json          # Chapter descriptions
│   ├── 2.Rectilinear Motion.json
│   ├── 5.Newton's Laws of Motion.json
│   └── ...
├── seed_problems/                     # Input CSV files
│   ├── 2-4.Kinematics.csv
│   ├── 5.Newton's Laws of Motion.csv
│   └── ...
├── run/                               # Main execution scripts
│   ├── main_ProblemGeneratorV6.py     # Main generator
│   ├── prompts.py                     # LLM prompts
│   ├── pg_helpers.py                  # Helper functions
│   ├── dataset_evaluator.py           # Quality metrics & HTML report
│   ├── defective_problem_filter.py    # Filter low-formula problems
│   ├── N_formula_collector.py         # Collect N-formula problems
│   └── ...
└── Physics_Evaluation_Report.html    # Generated analysis report
```

---

## 📈 Dataset Evaluation

### Generate Quality Report
```bash
cd run
python dataset_evaluator.py
```

**Output:** `Physics_Evaluation_Report.html` with:
- 📊 Global metrics (uniqueness, diversity, difficulty)
- 📉 Formula distribution & code complexity analysis
- 🗂️ Chapter-wise breakdowns with visualizations
- 🔍 Interactive plots (expandable sections)

**Key Metrics Tracked:**
- Text/Signature Uniqueness (%)
- Type-Token Ratio (vocabulary diversity)
- Avg Formulas per Problem
- Numerical Validity & Outliers
- Formula Count Distribution

---

## 🛠️ Utilities

### Filter Defective Problems
```bash
python defective_problem_filter.py
```
Removes problems with ≤1 formulas and saves them to `global_defective_problems.json`.

### Collect N-Formula Problems
```bash
python N_formula_collector.py
```
Collects all problems with exactly N formulas (configurable) into `global_{N}_formula_count.json`.

**Configuration:**
```python
# In N_formula_collector.py
TARGET_FORMULA_COUNT = 3  # Adjust as needed
```

---

## 🤝 Contributing

Contributions are welcome! To contribute:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

**Areas for Improvement:**
- Adding more physics chapters (Electromagnetism, Thermodynamics, etc.)
- Improving formula verification logic
- Multi-language problem generation
- Integration with educational platforms

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

## 🙏 Acknowledgments

- **Google Generative AI** (Gemini 2.5 Flash) for powering the LLM pipeline
- **Open-source physics formula databases** for structured domain knowledge
- **Contributors** who provided seed problems and validation feedback

---

## 📬 Contact

**Project Maintainer:** [er-ads](https://github.com/er-ads)

For questions, suggestions, or issues, please open an [Issue](https://github.com/er-ads/ProblemGenerationAgent/issues) or reach out via GitHub.

---

<div align="center">

**⭐ Star this repository if you find it useful!**

[View Live Report](https://er-ads.github.io/ProblemGenerationAgent/Physics_Evaluation_Report.html) • [Documentation](#) • [Issues](https://github.com/er-ads/ProblemGenerationAgent/issues)

</div>
