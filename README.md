# ProblemGenerationAgent ![Python](https://img.shields.io/badge/language-Python-blue)

A concise Python-based agent for automated problem generation. Ideal for educational platforms, assessment systems, or AI research where dynamic question creation is needed.

![Demo](https://your-demo-link.com/demo.gif)

---

## Table of Contents

- [File_Description](#File_Description)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)

---

## File_Description

Here are brief descriptions of the major files in this repository:

### main_ProblemGeneratorV5.py

- **Role and Overview:**  
  Serves as the main runner for generating physics problems. It coordinates the process using large language models (LLMs), chapter manifests, preset prompts, and helper functions.
- **Key Functional Steps:**  
  - Loads chapter information and initial problem/solution pairs.
  - Uses LLMs to analyze the provided problem/solution, extract relevant chapters, variables, and alternate scenarios.
  - Builds the set of available formulas from chosen chapters.
  - Runs a multi-iteration loop to generate new word problems using alternate scenarios.
  - Validates each generated problem for logical consistency and uniqueness.
  - Generates Python code to solve each new problem and evaluates code correctness by executing it.
  - Stores all validated, successful problems in a JSON file for future use.
- **Notable Dependencies:**  
  Relies on Google Generative AI (`google.generativeai`), local modules (`prompts.py`, `pg_helpers.py`), and JSON-based chapter/formula data files.
- **Input/Output:**  
  Takes structured JSON files, uses them within LLM prompt calls, and outputs results to JSON (`successful_problems.json`).
- **Error Handling:**  
  Includes retry logic for parsing/generation failures, checks for missing chapters/formulas, and structured exception handling during code execution.

### pg_helpers.py

- **Role and Overview:**  
  A utility module containing functions to support loading files, processing LLM outputs, validating generated problems, de-duplicating, and executing code.
- **Provided Helper Functions:**  
  - JSON loading and error-safe wrappers.
  - Cleaning/extracting code or JSON from LLM text responses.
  - Formula normalization and mapping-by-ID.
  - Problem signature computation for de-duplication.
  - Safe code execution and result validation.
  - Writing JSON output atomically.
- **Safety and Validation:**  
  Heavy use of validation logic for problem correctness, error reporting for JSON issues and execution failures, extensive exception logging.
- **Key Interactions:**  
  Streamlines data flow and guards against various forms of user/LLM error for the main generator script.

### prompts.py

- **Role and Overview:**  
  Encapsulates all templated prompt strings for communication with the LLM at different stages of problem generation.
- **Prompt Templates Provided:**  
  Includes prompt templates for analyzing Q/A pairs, verifying formulas, generating physics problems, retrying problem creation, generating Python code to solve those problems, and handling error corrections.
- **Customization and Extensibility:**  
  Easily adjustable for different kinds of physics topics, chapters, or educational levels; supports insertion of structured JSON and context for each LLM call in main_ProblemGeneratorV5.py.

### chapter_manifest.json

- **Role and Overview:**  
  Provides a catalog of physics chapters, each with descriptions and lists of formula names available for use.
- **Structure:**  
  Hierarchical JSON mapping chapters to descriptions and associated formula identifiers.
- **Usage:**  
  Used in main_ProblemGeneratorV5.py and prompts.py to select relevant chapters and pull formula lists for specific problem scenarios.

### 10.Rigid Body Dynamics.json

- **Role and Overview:**  
  Contains detailed information and Python implementations for formulas relevant to "Rigid Body Dynamics."
- **Structure:**  
  JSON array of formula objects, each including a formula ID, function name, docstring description, and complete Python code for direct use.
- **Usage:**  
  Formula IDs are referenced by the generator and code-solvers to match specific problem scenarios, enabling the assembly and evaluation of code snippets for physics calculations.



## Features

- 100% Python implementation
- Automated generation of diverse problem sets
- Easily extensible for custom question types
- Simple integration into other Python projects

## Installation

```bash
git clone https://github.com/er-ads/ProblemGenerationAgent.git
cd ProblemGenerationAgent
pip install -r requirements.txt
```

## Usage

```python
from problem_generation_agent import ProblemGenerator

generator = ProblemGenerator()
problem = generator.generate()
print(problem)
```

## Configuration

Configure parameters inside `config.py` to tailor problem generation to your needs.

## Contributing

Pull requests and suggestions are welcome! Please fork the repo and submit a PR.

## License

[MIT](LICENSE)

## Acknowledgments

- Inspired by open-source educational platforms
- Special thanks to contributors and issue reporters
