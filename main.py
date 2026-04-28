import argparse
import os
import random
import subprocess
import sys
import threading

from dotenv import load_dotenv
import google.generativeai as genai

try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
except ImportError:
    PYPERCLIP_AVAILABLE = False

try:
    from textual.app import App, ComposeResult
    from textual.containers import Container, Horizontal, VerticalScroll
    from textual.widgets import Static, Button
    from textual import work
    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False


GEMINI_MODEL = "gemini-3-flash-preview"
MAX_DIFF_LENGTH = 4000
SYSTEM_PROMPT = "You are a Git commit message expert. I will give you a git diff. Read it carefully. Generate ONE conventional commit message that describes ONLY the changes in that specific diff. Do not describe any tool, generator, or AI system. Do not make up context. Base the message solely on what you see in the diff. Format: type(scope): description. Types: feat, fix, docs, refactor, chore. Max 72 characters. Return ONLY the commit message with no explanation."

SPINNER_CHARS = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
DEFAULT_SPINNER_MESSAGES = [
    "Thinking...",
    "Analyzing diff...",
    "Reading changes...",
    "Crafting message...",
    "Consulting the git gods...",
    "Summoning commit wisdom...",
    "Processing...",
    "Almost there...",
]

def load_spinner_messages() -> list[str]:
    try:
        if os.path.exists("spinner_messages.txt"):
            with open("spinner_messages.txt", "r") as f:
                messages = []
                for line in f:
                    msg = line.strip()
                    if msg and not msg.endswith("..."):
                        msg = msg + "..."
                    if msg:
                        messages.append(msg)
            return messages if messages else DEFAULT_SPINNER_MESSAGES
    except Exception:
        pass
    return DEFAULT_SPINNER_MESSAGES

SPINNER_MESSAGES = load_spinner_messages()

BG = "#1a1a2e"
HEADER_BG = "#16213e"
ACCENT = "#e8624a"
TEXT_PRIMARY = "#e0e0e0"
TEXT_SECONDARY = "#888888"
SUCCESS = "#4caf7d"
ERROR = "#e85d4a"
BORDER = "#2d2d4e"
INPUT_BG = "#0f0f1a"

CSS = f"""
Screen {{
    background: {BG};
}}
#header-title {{
    color: #e8624a;
    text-style: bold;
}}
#header-subtitle {{
    color: {TEXT_SECONDARY};
}}
#staged-panel {{
    border: solid {BORDER};
    padding: 1;
    background: {BG};
}}
#staged-title {{
    color: {TEXT_SECONDARY};
    text-style: bold;
}}
#staged-list {{
    color: {SUCCESS};
}}
.divider {{
    height: 1;
    color: {BORDER};
}}
#message-panel {{
    border: solid {BORDER};
    padding: 1;
    background: {BG};
}}
#message-title {{
    color: {TEXT_SECONDARY};
    text-style: bold;
}}
#message-content {{
    color: {ACCENT};
    text-style: bold;
}}
#status {{
    color: {TEXT_SECONDARY};
}}
#status-generating {{
    color: {ACCENT};
    text-style: bold;
}}
#status-error {{
    color: {ERROR};
}}
#button-row {{
    align: center middle;
    height: auto;
    padding: 1 2;
}}
.btn {{
    color: {TEXT_SECONDARY};
    padding: 0 2;
    min-width: 18;
}}
.btn-selected {{
    background: {ACCENT};
    color: #ffffff;
    text-style: bold;
}}
.btn-disabled {{
    color: #444444;
}}
#footer-keys {{
    color: {TEXT_SECONDARY};
}}
"""

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI-powered git commit message generator")
    parser.add_argument("--apply", action="store_true", help="Automatically commit")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--tui", action="store_true", help="TUI mode")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Dry run")
    parser.add_argument("--dir", type=str, default=None, help="Directory")
    return parser.parse_args()


def get_staged_files(path: str | None = None) -> list[str]:
    try:
        result = subprocess.run(["git", "diff", "--staged", "--name-only"], capture_output=True, text=True, check=True, cwd=path, encoding="utf-8", errors="replace")
        return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    except subprocess.CalledProcessError:
        return []


def get_current_branch(path: str | None = None) -> str:
    try:
        result = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, check=True, cwd=path, encoding="utf-8", errors="replace")
        return result.stdout.strip() or "main"
    except subprocess.CalledProcessError:
        return "main"


def get_staged_diff(path: str | None = None) -> str:
    try:
        result = subprocess.run(["git", "diff", "--staged"], capture_output=True, text=True, check=True, cwd=path, encoding="utf-8", errors="replace")
        return result.stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: Failed to get staged diff.")
        sys.exit(1)


def check_staged_changes(diff: str) -> bool:
    if not diff.strip():
        print("No staged changes found.")
        sys.exit(0)
    return True


def truncate_diff(diff: str) -> str:
    return diff[:MAX_DIFF_LENGTH] + "\n\n[truncated]" if len(diff) > MAX_DIFF_LENGTH else diff


def get_gemini_api_key() -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable is not set.")
        sys.exit(1)
    return api_key


def call_gemini_api(diff: str, api_key: str) -> str:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name=GEMINI_MODEL, system_instruction=SYSTEM_PROMPT)
    try:
        response = model.generate_content(f"Git diff:\n{diff}")
        return response.text.strip() if response.text else ""
    except Exception:
        try:
            response = model.generate_content(f"Git diff:\n{diff}")
            return response.text.strip() if response.text else ""
        except Exception:
            return ""


def apply_git_commit(message: str, path: str | None = None) -> bool:
    try:
        subprocess.run(["git", "commit", "-m", message], check=True, cwd=path)
        return True
    except subprocess.CalledProcessError:
        return False


def run_interactive_cli(diff: str, api_key: str, path: str | None = None) -> None:
    files = get_staged_files(path)
    print("\nStaged files:")
    for f in files:
        print(f"  + {f}")
    print("\nGenerating...")
    msg = call_gemini_api(diff, api_key)
    print(f"\n{msg}")
    if input("\nCommit? [y/n]: ").strip().lower() == "y":
        if apply_git_commit(msg, path):
            print("Committed!")


if TEXTUAL_AVAILABLE:

    class CommitApp(App):
        Title = "ai-commit"
        CSS = CSS
        BINDINGS = [
            ("g", "generate", "Generate"),
            ("a", "apply", "Apply"),
            ("c", "copy", "Copy"),
            ("q", "quit", "Quit"),
            ("left", "left", "Left"),
            ("right", "right", "Right"),
            ("enter", "enter", "Enter"),
            ("escape", "quit", "Quit"),
        ]

        def __init__(self, diff: str, api_key: str, path: str | None = None):
            super().__init__()
            self.diff = diff
            self.api_key = api_key
            self.path = path
            self.commit_message = ""
            self.staged_files = get_staged_files(path)
            self.branch = get_current_branch(path)
            self.generating = False
            self.selected = 0
            self.button_labels = ["Generate", "Apply & Commit", "Copy", "Quit"]
            self.spinner_char_index = 0
            self.current_spinner_message = ""
            self.spinner_timer = None

        def compose(self) -> ComposeResult:
            yield Static(f"⬡ ai-commit", id="header-title")
            yield Static(f"│ {self.branch}", id="header-subtitle")
            
            with VerticalScroll(id="main"):
                with Container(id="staged-panel"):
                    yield Static("Staged Changes", id="staged-title")
                    if self.staged_files:
                        yield Static("\n".join(f"+ {f}" for f in self.staged_files), id="staged-list")
                    else:
                        yield Static("No staged changes", id="staged-list")
                yield Static("─" * 40, classes="divider")
                with Container(id="message-panel"):
                    yield Static("Generated Message", id="message-title")
                    yield Static("", id="message-content")
                yield Static("Ready", id="status")
            
            yield Static("", id="buttons")
            
            yield Static("g Generate  a Apply  c Copy  q Quit  ← → Navigate", id="footer-keys")

        def on_mount(self) -> None:
            self._render_buttons()

        def _render_buttons(self) -> None:
            container = self.query_one("#buttons", Static)
            buttons = []
            
            for i, label in enumerate(self.button_labels):
                if self.selected == i:
                    prefix = "▶"
                    buttons.append(f"{prefix} {label}")
                else:
                    buttons.append(f" {label} ")
            
            container.update("   ".join(buttons))

        def on_mount_action(self) -> None:
            if not self.staged_files:
                self.query_one("#status", Static).update("No staged changes. Run git add first.")
                self.query_one("#status").add_class("status-error")

        def action_left(self) -> None:
            self.selected = (self.selected - 1) % 4
            self._render_buttons()

        def action_right(self) -> None:
            self.selected = (self.selected + 1) % 4
            self._render_buttons()

        def action_enter(self) -> None:
            if self.selected == 0:
                self.action_generate()
            elif self.selected == 1:
                self.action_apply()
            elif self.selected == 2:
                self.action_copy()
            elif self.selected == 3:
                self.action_quit()

        def action_generate(self) -> None:
            if self.generating or not self.staged_files:
                return
            self.generating = True
            self.spinner_char_index = 0
            self.current_spinner_message = random.choice(SPINNER_MESSAGES)
            
            self.query_one("#status", Static).add_class("status-generating")
            
            self.spinner_timer = self.set_interval(0.6, self._update_spinner)
            
            def worker():
                msg = call_gemini_api(self.diff, self.api_key)
                self.call_later(self._on_generated, msg)
            
            threading.Thread(target=worker, daemon=True).start()

        def _update_spinner(self) -> None:
            spinner_char = SPINNER_CHARS[self.spinner_char_index % len(SPINNER_CHARS)]
            self.query_one("#status", Static).update(f"{spinner_char} {self.current_spinner_message}")
            self.spinner_char_index += 1

        def _on_generated(self, message: str) -> None:
            if self.spinner_timer:
                self.spinner_timer.stop()
                self.spinner_timer = None
            self.commit_message = message or "Failed to generate"
            self.query_one("#message-content", Static).update(self.commit_message)
            self.query_one("#status", Static).update("✓ Done")
            self.query_one("#status").remove_class("status-generating")
            self.generating = False
            self._render_buttons()

        def action_apply(self) -> None:
            if not self.commit_message:
                return
            if apply_git_commit(self.commit_message, self.path):
                self.query_one("#status", Static).update("Committed!")
                self.exit()
            else:
                self.query_one("#status", Static).update("Commit failed")
                self.query_one("#status").add_class("status-error")

        def action_copy(self) -> None:
            if not self.commit_message:
                return
            if PYPERCLIP_AVAILABLE:
                pyperclip.copy(self.commit_message)
                self.query_one("#status", Static).update("Copied!")
            else:
                self.query_one("#status", Static).update("Copy not available")
            self.call_later(self._reset_status)

        def _reset_status(self) -> None:
            self.query_one("#status", Static).update("Done")

        def action_quit(self) -> None:
            self.exit()


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