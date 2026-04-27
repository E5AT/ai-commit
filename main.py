import argparse
import os
import subprocess
import sys

from dotenv import load_dotenv
import google.generativeai as genai

try:
    from textual.app import App, ComposeResult
    from textual.containers import Container, Horizontal
    from textual.widgets import Header, Button, Static, Input, Footer
    from textual import on
    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False


GEMINI_MODEL = "gemini-3-flash-preview"
MAX_DIFF_LENGTH = 4000
SYSTEM_PROMPT = "You are a Git commit message expert. I will give you a git diff. Read it carefully. Generate ONE conventional commit message that describes ONLY the changes in that specific diff. Do not describe any tool, generator, or AI system. Do not make up context. Base the message solely on what you see in the diff. Format: type(scope): description. Types: feat, fix, docs, refactor, chore. Max 72 characters. Return ONLY the commit message with no explanation."


CSS = """
Static#title {
    dock: top;
    height: 3;
    content-align: center middle;
    color: $accent;
    text-style: bold;
    background: $surface;
    border: solid $accent;
}
Static#label {
    color: $text-muted;
    text-style: bold;
}
Container#summary {
    border: solid $primary;
    padding: 1;
}
Static#message {
    color: $success;
    text-style: bold;
    content-align: center middle;
}
Button {
    min-width: 16;
}
Button:focus {
    background: $accent;
    color: $text;
}
Button:hover {
    text-style: bold;
}
#actions {
    align: center middle;
}
#custom_row {
    align: center middle;
}
Input {
    border: solid $primary;
}
Input:focus {
    border: solid $accent;
}
"""

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
        "--interactive",
        "-i",
        action="store_true",
        help="Interactive mode",
    )
    parser.add_argument(
        "--tui",
        action="store_true",
        help="TUI mode (requires textual)",
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


def get_staged_summary(path: str | None = None) -> str:
    try:
        result = subprocess.run(
            ["git", "diff", "--staged", "--stat"],
            capture_output=True,
            text=True,
            check=True,
            cwd=path,
            encoding="utf-8",
            errors="replace",
        )
        if result.stdout.strip():
            lines = result.stdout.strip().split("\n")
            return "\n".join(lines[-3:]) if len(lines) > 3 else result.stdout.strip()
        return "No staged changes"
    except subprocess.CalledProcessError:
        return "No staged changes"


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
            raise Exception("Empty response")
        return response.text.strip()
    except Exception:
        try:
            response = model.generate_content(f"Here is the git diff. Write a commit message for these exact changes only:\n{diff}")
            if response.text is None:
                raise Exception("Empty response")
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
    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to commit. {e}")
        sys.exit(1)


def run_interactive_cli(diff: str, api_key: str, path: str | None = None) -> None:
    summary = get_staged_summary(path)
    print("\nStaged changes:")
    print(summary)
    input("\nPress Enter to generate commit message...")

    while True:
        print("\nGenerating commit message...")
        commit_message = call_gemini_api(diff, api_key)
        print(f"\n{commit_message}")

        while True:
            response = input("\n[y]es / [n]o / [r]egenerate: ").strip().lower()
            if response == "y":
                apply_git_commit(commit_message, path)
                print(f"Committed!")
                return
            elif response == "n":
                custom = input("Custom message (or enter to cancel): ").strip()
                if custom:
                    apply_git_commit(custom, path)
                    print(f"Committed!")
                    return
                break
            elif response == "r":
                break
            else:
                print("Enter y, n, or r")


if TEXTUAL_AVAILABLE:

    class CommitApp(App):
        Title = "ai-commit"
        SubTitle = "Commit Message Generator"
        CSS = CSS
        BINDINGS = [
            ("g", "generate", "Generate"),
            ("enter", "apply", "Apply"),
            ("r", "regenerate", "Regenerate"),
            ("left", "focus_left", "Left"),
            ("right", "focus_right", "Right"),
            ("escape", "cancel", "Cancel"),
            ("ctrl+c", "cancel", "Cancel"),
        ]

        def __init__(self, diff: str, api_key: str, path: str | None = None):
            super().__init__()
            self.diff = diff
            self.api_key = api_key
            self.path = path
            self.commit_message = ""
            self.button_order = ["generate"]
            self.current_button = 0

        def compose(self) -> ComposeResult:
            yield Header()
            yield Static("ai-commit", id="title")
            yield Static("Staged changes:", id="label")
            with Container(id="summary"):
                yield Static(get_staged_summary(self.path), id="summary_text")
            yield Button("Generate Message", id="generate", variant="primary")
            yield Static("", id="message")
            with Horizontal(id="actions"):
                yield Button("Apply ->", id="apply", variant="success", disabled=True)
                yield Button("Regenerate", id="regenerate", variant="warning", disabled=True)
                yield Button("Cancel", id="cancel", variant="error")
            yield Static("", id="custom_label")
            with Horizontal(id="custom_row"):
                yield Input(placeholder="Type custom commit message...", id="custom_input", disabled=True)
                yield Button("Use Custom", id="use_custom", variant="default", disabled=True)
            yield Footer()

        def on_mount(self) -> None:
            self.query_one("#actions").display = False
            self.query_one("#custom_row").display = False
            self.query_one("#custom_label").display = False
            self.query_one("#message").display = False

        def on_button_pressed(self, event: Button.Pressed) -> None:
            button_id = event.button.id

            if button_id == "generate":
                self.action_generate()
            elif button_id == "apply":
                self.action_apply()
            elif button_id == "regenerate":
                self.action_regenerate()
            elif button_id == "use_custom":
                self.action_use_custom()
            elif button_id == "cancel":
                self.action_cancel()

        def action_generate(self) -> None:
            self.commit_message = call_gemini_api(self.diff, self.api_key)
            self.query_one("#message", Static).update(f"[ {self.commit_message} ]")
            self.query_one("#message").display = True
            self.query_one("#actions").display = True
            self.query_one("#custom_row").display = True
            self.query_one("#custom_label").display = True
            self.query_one("#apply", Button).disabled = False
            self.query_one("#regenerate", Button).disabled = False
            self.query_one("#custom_input", Input).disabled = False
            self.query_one("#use_custom", Button).disabled = False
            self.query_one("#generate", Button).disabled = True
            self.button_order = ["apply", "regenerate", "cancel"]
            self.current_button = 0
            self.set_focus(self.query_one("#apply"))

        def action_apply(self) -> None:
            if self.commit_message:
                apply_git_commit(self.commit_message, self.path)
                self.query_one("#message", Static).update("[ COMMITTED! ]")
                self.exit()

        def action_regenerate(self) -> None:
            if self.commit_message:
                self.query_one("#message", Static).update("[ Regenerating... ]")
                self.commit_message = call_gemini_api(self.diff, self.api_key)
                self.query_one("#message", Static).update(f"[ {self.commit_message} ]")

        def action_use_custom(self) -> None:
            custom_msg = self.query_one("#custom_input", Input).value.strip()
            if custom_msg:
                apply_git_commit(custom_msg, self.path)
                self.query_one("#message", Static).update(f"[ COMMITTED: {custom_msg} ]")
                self.exit()

        def action_cancel(self) -> None:
            self.exit()

        def action_focus_left(self) -> None:
            if self.current_button > 0:
                self.current_button -= 1
                self._focus_button()

        def action_focus_right(self) -> None:
            if self.current_button < len(self.button_order) - 1:
                self.current_button += 1
                self._focus_button()

        def _focus_button(self) -> None:
            btn_id = self.button_order[self.current_button]
            self.set_focus(self.query_one(f"#{btn_id}"))


def main() -> None:
    load_dotenv()
    args = parse_args()

    diff = get_staged_diff(args.dir)
    check_staged_changes(diff)
    diff = truncate_diff(diff)

    api_key = get_gemini_api_key()

    if args.tui and TEXTUAL_AVAILABLE:
        app = CommitApp(diff, api_key, args.dir)
        app.run()
        return
    elif args.interactive:
        if TEXTUAL_AVAILABLE:
            app = CommitApp(diff, api_key, args.dir)
            app.run()
        else:
            run_interactive_cli(diff, api_key, args.dir)
        return

    commit_message = call_gemini_api(diff, api_key)

    print(commit_message)

    if args.apply:
        apply_git_commit(commit_message, args.dir)


if __name__ == "__main__":
    main()