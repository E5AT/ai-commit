import argparse
import os
import subprocess
import sys

from dotenv import load_dotenv
import google.generativeai as genai


GEMINI_MODEL = "gemini-3-flash-preview"
MAX_DIFF_LENGTH = 4000
SYSTEM_PROMPT = "You are a Git commit message expert. I will give you a git diff. Read it carefully. Generate ONE conventional commit message that describes ONLY the changes in that specific diff. Do not describe any tool, generator, or AI system. Do not make up context. Base the message solely on what you see in the diff. Format: type(scope): description. Types: feat, fix, docs, refactor, chore. Max 72 characters. Return ONLY the commit message with no explanation."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI-powered git commit message generator"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Automatically commit with the generated message",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Print message without committing (default behavior)",
    )
    parser.add_argument(
        "--dir",
        type=str,
        default=None,
        help="Directory to run git diff in",
    )
    return parser.parse_args()


def get_staged_diff(path: str | None = None) -> str:
    try:
        result = subprocess.run(
            ["git", "diff", "--staged"],
            capture_output=True,
            text=True,
            check=True,
            cwd=path,
            encoding="utf-8",
            errors="replace",
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to get staged diff. Are you in a git repository?")
        sys.exit(1)
    except FileNotFoundError:
        print("Error: git is not installed or not in PATH.")
        sys.exit(1)


def check_staged_changes(diff: str) -> bool:
    if not diff.strip():
        print("No staged changes found.")
        sys.exit(0)
    return True


def truncate_diff(diff: str) -> str:
    if len(diff) > MAX_DIFF_LENGTH:
        return diff[:MAX_DIFF_LENGTH] + "\n\n[diff truncated for brevity]"
    return diff


def get_gemini_api_key() -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable is not set.")
        sys.exit(1)
    return api_key


def call_gemini_api(diff: str, api_key: str) -> str:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=SYSTEM_PROMPT,
    )

    try:
        response = model.generate_content(f"Here is the git diff. Write a commit message for these exact changes only:\n{diff}")
        if response.text is None:
            print("Error: Gemini returned an empty response. Please try again.")
            sys.exit(1)
        return response.text.strip()
    except Exception:
        try:
            response = model.generate_content(f"Here is the git diff. Write a commit message for these exact changes only:\n{diff}")
            if response.text is None:
                print("Error: Gemini returned an empty response. Please try again.")
                sys.exit(1)
            return response.text.strip()
        except Exception:
            print("Error: Failed to generate commit message. Please try again.")
            sys.exit(1)


def apply_git_commit(message: str, path: str | None = None) -> None:
    try:
        subprocess.run(
            ["git", "commit", "-m", message],
            check=True,
            cwd=path,
        )
        print(f"Committed: {message}")
    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to commit. {e}")
        sys.exit(1)


def main() -> None:
    load_dotenv()
    args = parse_args()

    diff = get_staged_diff(args.dir)
    check_staged_changes(diff)
    diff = truncate_diff(diff)

    api_key = get_gemini_api_key()
    commit_message = call_gemini_api(diff, api_key)

    print(commit_message)

    if args.apply:
        apply_git_commit(commit_message, args.dir)


if __name__ == "__main__":
    main()
