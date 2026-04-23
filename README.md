# ai-commit

AI-powered git commit message generator that creates conventional commits from your staged changes using Google's Gemini API.

## Requirements

- Python 3.10+
- Git
- Gemini API key

## Installation

```bash
# Clone or download this repository
cd ai-commit

# Install dependencies
pip install -r requirements.txt
```

## Gemini API Key Setup

1. Get an API key from [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Create a `.env` file in the project root:

```bash
GEMINI_API_KEY=your_api_key_here
```

Or export it as an environment variable:

```bash
export GEMINI_API_KEY=your_api_key_here
```

## Usage

```bash
# Stage your changes
git add .

# Generate a commit message (default: dry-run)
ai-commit
# Output: feat: add user authentication module

# Interactive mode - show changes, generate message, confirm
ai-commit -i

# Automatically commit with the generated message
ai-commit --apply

# Run from a specific directory
ai-commit --dir /path/to/repo

# Show help
ai-commit --help
```

## CLI Options

| Flag | Description |
|------|-------------|
| `--apply` | Automatically commit with the generated message |
| `--interactive`, `-i` | Interactive mode: show changes, generate message, confirm |
| `--dry-run` | Print message without committing (default) |
| `--dir` | Directory to run git diff in |

## Global CLI Setup (WSL / Linux)

To use `ai-commit` as a global command from anywhere:

1. Create a wrapper script at `/path/to/ai-commit/ai-commit`:

```bash
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CALLING_DIR="$PWD"
cd "$SCRIPT_DIR" && python main.py --dir "$CALLING_DIR" "$@"
```

2. Create a symlink in your PATH:

```bash
sudo ln -s /path/to/ai-commit/ai-commit /usr/local/bin/ai-commit

# Make sure the shell script is executable
chmod +x /path/to/ai-commit/ai-commit
```

After this you can run `ai-commit` from any git repository without specifying the full path.

> This setup was built and tested on WSL (Windows Subsystem for Linux) with Ubuntu.

## Project Structure

```
ai-commit/
├── main.py           # Main entry point
├── requirements.txt  # Dependencies
├── .env              # API key storage (not committed)
├── tests/            # Test suite (50 tests, 96% coverage)
│   ├── conftest.py
│   ├── test_api_calls.py
│   ├── test_edge_cases.py
│   ├── test_git_operations.py
│   ├── test_main_flow.py
│   └── test_parse_args.py
└── README.md
```

## Running Tests

```bash
pytest
```

With coverage:

```bash
pytest --cov=. --cov-report=term-missing
```

## How It Works

1. Runs `git diff --staged` to capture your staged changes
2. Truncates diff to 4000 characters (prevents API limits)
3. Sends the diff to Gemini 3 Flash (gemini-3-flash-preview) with a system prompt
4. Returns a conventional commit message in `type(scope): description` format
5. Optionally executes `git commit` with the generated message

## Why Gemini API

Gemini 3 Flash (gemini-3-flash-preview) was chosen for its generous free tier, which makes this tool practical for daily use without any cost. No paid subscription required.

## License

MIT