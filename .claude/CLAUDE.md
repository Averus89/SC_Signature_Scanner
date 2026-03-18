# CLAUDE.md — Python Project Rules for Claude Code
# Author: Mallachi
# Version: 1.0.0

> This document defines behavioral rules, coding standards, and operational modes for Claude Code when working on Python projects.

---
## The 15 rules of coding to be followed during coding, testing, and code review
- Keep It Simple, Stupid (KISS): Avoid unnecessary complexity; simple code is easier to maintain and debug.
- Don’t Repeat Yourself (DRY): Avoid duplication by abstracting common functionality into reusable components.
- You Aren't Gonna Need It (YAGNI): Do not add functionality until it is necessary to prevent over-engineering.
- Separation of Concerns (SoC): Divide code into distinct sections, where each section addresses a separate concern or functionality.
- Clean Code & Readability: Code is read more often than it is written; prioritize clear naming conventions and structure.
- Comment the "Why", Not the "What": Use comments to explain the reasoning behind complex logic rather than just describing the code itself.
- Avoid Premature Optimization: Focus on making code work correctly first; optimize only when performance profiling reveals a bottleneck.
- Consistent Standards: Adhere to a unified style guide so the code looks as if it were written by a single person.
- SOLID Principles: Follow object-oriented design principles to make software designs more understandable, flexible, and maintainable.
- Unit Testing: Write automated tests for your code to ensure functionality and prevent regressions.
- Code Reviews: Have peers review your code to catch bugs early and share knowledge.
- Handle Errors Gracefully: Anticipate potential failures and handle exceptions, rather than letting the application crash.
- Version Control: Use systems like Git to track changes and collaborate effectively.
- Delete Unnecessary Code: Remove unused variables, dead code, and obsolete comments to reduce technical debt.
- I have .


## OPERATIONAL MODES

### Default Mode: Advisory
Claude Code operates in **advisory mode** by default:
- Explain approach, complexity, trade-offs
- Present implementation options when multiple exist
- **Do NOT write or edit code until explicitly instructed**
- Exploratory phrases ("Is it possible...", "How would I...", "What's the best way...") = discussion only
- Action phrases ("Add...", "Implement...", "Change...", "Go ahead", "Do it") = permission granted

### Training Wheels Protocol 🎓
**Activated by:** Including `[TRAINING WHEELS]` or `[TWP]` in the message.

When active, Claude Code becomes a coding instructor:

**Teaching Principles:**
- Assume zero prior knowledge unless demonstrated otherwise
- Explain the "why" before the "how"
- Break complex concepts into digestible steps
- Use analogies from real-world domains (industrial, mechanical, process engineering)
- Celebrate small wins without being patronizing

**Response Structure:**
1. **Concept Introduction** — What are we learning and why it matters
2. **Breakdown** — Step-by-step explanation with rationale
3. **Example** — Minimal working code demonstrating the concept
4. **Exercise** — A small challenge for the learner to try
5. **Common Pitfalls** — What typically trips people up
6. **Next Steps** — What to explore after mastering this

**Code Presentation:**
- Every line of code gets a comment explaining what it does
- Show "wrong" examples alongside correct ones when illustrating pitfalls
- Build up from simple to complex (don't dump full solutions)
- Offer to explain any line in more detail on request

**Pacing:**
- Ask "Ready to continue?" before moving to next concept
- Offer recap summaries at natural breakpoints
- Adjust depth based on learner's questions

**Deactivation:** Training Wheels Protocol remains active until `[/TWP]` or `[END TRAINING]` is sent, or a new conversation begins.

---

## WORKFLOW RULES

### Before Writing Any Code
1. **Confirm approach** — State what you intend to do and wait for approval
2. **Present options** — If multiple valid approaches exist, list them with trade-offs
3. **Check for existing patterns** — Review project structure before introducing new patterns

### When Implementing Code Changes
Every implementation MUST include:
- [ ] Version bump in `config.py` (or equivalent version file)
- [ ] `DEVLOG.md` update with change description
- [ ] Run linting (`ruff check --fix . && ruff format .`)

### Investigation Protocol
When asked to investigate errors or problems:
1. **Present multiple possible causes first** — Don't assume the first theory is correct
2. **Ask which to explore** — Let the user direct the investigation
3. **Reading code to investigate IS coding** — Requires explicit permission before opening files

### Project Utilities
Include `clean.py` in all Python projects with these defaults:
- Removes `__pycache__/` directories
- Removes `*.pyc`, `*.pyo` files
- Removes `build/`, `dist/`, `*.egg-info/` directories
- Removes `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`

### Project Documentation
Always incorporate `TODO.md` and `Devlog.md` in projects:
- **At session start** — Read these files to understand current state and pending tasks
- **Writing code** — When implementing or updating code, always update `Todo.md` and `Devlog.md` before and after coding, in order to conserve project momentum, in case of process shutdown from external events.
- **TODO.md** — Track tasks, verified patterns, and known issues
- **Devlog.md** — Document architecture decisions, changelog, and API references

---

## PYTHON CODING STANDARDS

### Style (PEP 8 Baseline)
```
Indentation:       4 spaces (never tabs)
Line length:       88 characters (Ruff/Black standard)
Quotes:            Double quotes for strings (single acceptable for dict keys)
Trailing commas:   Yes, in multi-line structures
Blank lines:       2 before top-level definitions, 1 between methods
```

### Naming Conventions
```
variables:         snake_case
functions:         snake_case
classes:           PascalCase
constants:         UPPER_SNAKE_CASE
private:           _single_leading_underscore
"internal":        __double_leading_underscore (name mangling)
modules:           short, lowercase, underscores if needed
```

### Import Order (enforced by Ruff isort)
```python
# 1. Standard library
import os
import sys
from pathlib import Path

# 2. Third-party packages
import pandas as pd
from openpyxl import Workbook

# 3. Local/project imports
from mypackage import module
from mypackage.submodule import function
```

### Type Hints (Required)
Use modern syntax (Python 3.10+):
```python
# YES - Modern syntax
def process(items: list[str], count: int | None = None) -> dict[str, int]:
    ...

# NO - Legacy typing module
from typing import List, Dict, Optional
def process(items: List[str], count: Optional[int] = None) -> Dict[str, int]:
    ...
```

**Type hint requirements:**
- All public functions and methods: parameters + return type
- Class attributes in `__init__` or as class variables
- Module-level variables that aren't obvious
- Private functions: optional but encouraged

**Complex types — use type aliases:**
```python
type ComplianceResult = dict[str, list[tuple[str, bool, str]]]
type InspectionRecord = dict[str, str | int | float | None]
```

### Docstrings (Google Style)
```python
def analyze_inspection(
    report_path: Path,
    standard: str = "IEC 60079-17",
) -> ComplianceResult:
    """Analyze an inspection report against a compliance standard.

    Parses the PDF report and evaluates each checklist item against
    the specified standard's requirements.

    Args:
        report_path: Path to the PDF inspection report.
        standard: Compliance standard to evaluate against.
            Defaults to IEC 60079-17.

    Returns:
        Dictionary mapping section names to lists of
        (item_id, passed, notes) tuples.

    Raises:
        FileNotFoundError: If report_path does not exist.
        ValueError: If standard is not recognized.

    Example:
        >>> result = analyze_inspection(Path("report.pdf"))
        >>> result["Section 1"]
        [("1.1", True, ""), ("1.2", False, "Missing documentation")]
    """
```

### Error Handling
```python
# GOOD - Specific exceptions, focused try blocks
try:
    data = load_config(config_path)
except FileNotFoundError:
    logger.error(f"Config file not found: {config_path}")
    raise
except json.JSONDecodeError as e:
    logger.error(f"Invalid JSON in config: {e}")
    raise ConfigurationError(f"Malformed config file: {config_path}") from e

# BAD - Broad exception, swallows errors
try:
    data = load_config(config_path)
    process(data)
    save_results(data)
except Exception:
    print("Something went wrong")
```

**Exception rules:**
- Never use bare `except:` — always specify exception type
- Use `except Exception` only at top-level handlers
- Chain exceptions with `raise ... from e` to preserve context
- Create custom exceptions for domain-specific errors

### Logging
```python
import logging

# Module-level logger (not root logger)
logger = logging.getLogger(__name__)

# In functions
logger.debug("Processing %d items", len(items))  # Lazy formatting
logger.info("Analysis complete: %s", summary)
logger.warning("Threshold exceeded: %.2f > %.2f", value, limit)
logger.error("Failed to process: %s", filename)
logger.exception("Unhandled error during processing")  # In except block only
```

**Logging rules:**
- Use `__name__` for logger names (creates hierarchy)
- Use lazy formatting (`%s`) not f-strings in log calls
- Configure logging at application entry point only
- Libraries should NEVER configure logging (only add NullHandler)
- Use `logger.exception()` in except blocks (captures stack trace)

---

## PROJECT STRUCTURE

### Standard Layout (src-layout)
```
project-name/
├── src/
│   └── package_name/
│       ├── __init__.py
│       ├── __main__.py      # Entry point for `python -m package_name`
│       ├── config.py        # Version, constants, configuration
│       ├── core.py          # Main business logic
│       └── utils.py         # Helper functions
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # pytest fixtures
│   ├── test_core.py
│   └── test_utils.py
├── docs/                    # Optional: documentation
├── scripts/                 # Optional: standalone scripts
├── .gitignore
├── clean.py                 # Project cleanup utility
├── DEVLOG.md               # Development log
├── LICENSE
├── pyproject.toml          # Project configuration (single source of truth)
└── README.md
```

### For Smaller/Script Projects
```
project-name/
├── package_name/
│   ├── __init__.py
│   ├── main.py
│   └── config.py
├── tests/
├── clean.py
├── DEVLOG.md
├── pyproject.toml
└── README.md
```

---

## PYPROJECT.TOML TEMPLATE

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "project-name"
version = "0.1.0"
description = "Brief project description"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}
authors = [
    {name = "Mallachi"}
]
keywords = ["relevant", "keywords"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]
dependencies = [
    # Runtime dependencies here
]

[project.optional-dependencies]
dev = [
    "ruff>=0.4.0",
    "mypy>=1.10.0",
    "pytest>=8.0.0",
    "pytest-cov>=5.0.0",
]

[project.scripts]
# command-name = "package_name.module:function"

[tool.setuptools.packages.find]
where = ["src"]

# ============================================================================
# RUFF CONFIGURATION
# ============================================================================
[tool.ruff]
target-version = "py310"
line-length = 88
indent-width = 4

exclude = [
    ".git",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "__pycache__",
    "build",
    "dist",
]

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # Pyflakes
    "I",      # isort
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "UP",     # pyupgrade
    "SIM",    # flake8-simplify
    "TCH",    # flake8-type-checking
    "PTH",    # flake8-use-pathlib
    "PL",     # pylint
    "RUF",    # Ruff-specific rules
]

ignore = [
    "E501",   # Line too long (handled by formatter)
    "PLR0913", # Too many arguments (sometimes necessary)
    "PLR2004", # Magic value comparison (often fine)
]

# Allow autofix for all enabled rules
fixable = ["ALL"]
unfixable = []

[tool.ruff.lint.isort]
known-first-party = ["package_name"]
force-single-line = false
lines-after-imports = 2

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
skip-magic-trailing-comma = false
line-ending = "auto"
docstring-code-format = true

# ============================================================================
# MYPY CONFIGURATION
# ============================================================================
[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_ignores = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
strict_optional = true
no_implicit_reexport = true

# Gradually enable for existing projects:
# disallow_untyped_defs = false  # Start here
# disallow_incomplete_defs = true
# check_untyped_defs = true

[[tool.mypy.overrides]]
module = ["tests.*"]
disallow_untyped_defs = false

# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = "-v --tb=short"
```

---

## OUTPUT STANDARDS

### Ex Checklist AI Reports
Generate as Word document with:
- **Header:** Client name, Workorder #, Project responsible, Client contact, Review date
- **Proper report formatting:** Section headers, tables, compliance matrices
- Follow corporate document standards

### General Documentation
- README.md: Purpose, installation, usage, configuration
- DEVLOG.md: Chronological development notes, decisions, issues
- Inline comments: Explain "why", not "what"

---

## QUICK REFERENCE

### Ruff Commands
```bash
ruff check .              # Lint
ruff check --fix .        # Lint and autofix
ruff format .             # Format
ruff check --fix . && ruff format .  # Full cleanup
```

### Type Checking
```bash
mypy src/                 # Check types
mypy --strict src/        # Strict mode
```

### Testing
```bash
pytest                    # Run tests
pytest -v                 # Verbose
pytest --cov=src          # With coverage
pytest -x                 # Stop on first failure
```

---

## ATTRIBUTION

All code and documentation produced under these rules:
- Credit: **Mallachi**
- Include in file headers, README, and about dialogs where appropriate

---

*End of CLAUDE.md*