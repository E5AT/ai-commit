# AI Commit - Agent Guidelines

This project is a Python CLI tool. The following guidelines apply to all code.

## Setup Commands
- **Install dependencies**: `pip install -r requirements.txt`
- **Run the tool**: `python main.py`
- **Run with --apply flag**: `python main.py --apply`
- **Run with --dry-run flag**: `python main.py --dry-run`

## Code Style Guidelines

### General Principles
- Use Python 3.10+
- Keep all code in a single `main.py` file
- Keep functions small and focused (single responsibility)
- Write self-documenting code with clear variable/function names
- Handle errors explicitly; never silently catch exceptions

### Formatting
- Use 4 spaces for indentation
- Use double quotes for strings
- Maximum line length: 88 characters
- Add type hints to all function signatures

### Naming Conventions
- Variables/functions: snake_case
- Constants: SCREAMING_SNAKE_CASE
- Classes: PascalCase

### Error Handling
- Always print a human-friendly message before exiting
- Use sys.exit(1) for errors, sys.exit(0) for clean exits
- Never use bare except clauses

### Environment Variables
- GEMINI_API_KEY must be read from os.environ
- If missing, print: "Error: GEMINI_API_KEY environment variable is not set."
- Then exit with code 1

### Git Commit Messages
- Use conventional commits: type(scope): description
- Types: feat, fix, docs, refactor, chore
- Keep subject line under 72 characters

## File Organization
- main.py — single entry point with all logic
- requirements.txt — pinned dependencies
- README.md — usage documentation
