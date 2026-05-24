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
    from textual.widgets import Static
    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False


GEMINI_MODEL = "gemini-3-flash-preview"
MAX_DIFF_LENGTH = 4000
SYSTEM_PROMPT = "You are an expert Git commit message writer with deep knowledge of conventional commits. You will receive a git diff output. Your job is to analyze it carefully and write exactly one commit message.\n\nSTRICT RULES:\n- Read the diff line by line before writing anything\n- The message must describe what the diff actually does, not what the project is\n- Never mention AI, generators, tools, or anything not visible in the diff\n- Never invent context or assumptions\n- If the diff adds files: use feat or docs\n- If the diff modifies logic: use fix or refactor\n- If the diff touches config, build files, gitignore, dependencies: use chore\n- If the diff only changes comments or documentation: use docs\n\nFORMAT: type(scope): description\n- type: feat, fix, docs, refactor, chore, test, style\n- scope: the module, folder, or feature area affected (e.g. auth, cart, algorithms, ui) — infer it from the file paths in the diff\n- description: short imperative sentence, present tense, no capital first letter, no period at the end\n- Full message must be under 72 characters\n\nEXAMPLES:\n- feat(cart): add product quantity validation\n- fix(auth): handle null token on logout\n- docs(algorithms): add sorting algorithm reference links\n- chore(deps): pin google-generativeai to 0.8.3\n- refactor(ui): extract button component from main view\n\nReturn ONLY the commit message. No explanation, no markdown, no quotes, no punctuation at the end."

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

BG = "#0d0d0d"
ACCENT = "#e8624a"
TEXT_DIM = "#333333"
TEXT_MID = "#444444"
TEXT_LIGHT = "#555555"
TEXT_FILE = "#bbbbbb"
SUCCESS = "#4caf7d"
ERROR = "#e24b4a"
BORDER = "#1e1e1e"

CSS = f"""
Screen {{
    background: {BG};
    overflow-y: hidden;
}}
#app {{
    width: 100%;
}}
.hline {{
    height: 1;
    background: {BORDER};
}}
#header {{
    height: 1;
    dock: top;
    background: {BG};
}}
.section-label {{
    color: {TEXT_MID};
}}
#file-count {{
    color: {TEXT_LIGHT};
}}
#file-list {{
    color: {TEXT_FILE};
}}
#commit-list {{
    color: {TEXT_FILE};
}}
.commit-placeholder {{
    color: {TEXT_DIM};
    text-style: italic;
}}
.commit-message {{
    color: {ACCENT};
    text-style: bold;
}}
#spinner-line {{
    color: {ACCENT};
}}
.btn {{
    color: {TEXT_MID};
}}
.btn-selected {{
    color: {ACCENT};
    text-style: bold;
}}
.branch {{
    color: {TEXT_MID};
}}
.bullet {{
    color: {ACCENT};
}}
.error-text {{
    color: {ERROR};
}}
.success-text {{
    color: {SUCCESS};
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
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"


def apply_git_commit(message: str, path: str | None = None) -> bool:
    try:
        subprocess.run(["git", "commit", "-m", message], check=True, cwd=path)
        return True
    except subprocess.CalledProcessError:
        return False


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
            self.committing = False
            self.selected = 0
            self.button_labels = ["Generate", "Apply", "Copy", "Quit"]
            self.spinner_char_index = 0
            self.current_spinner_message = ""
            self.spinner_timer = None

        def compose(self) -> ComposeResult:
            yield Static("", id="header")
            yield Static("", classes="hline")
            yield Static("❯ STAGED CHANGES", classes="section-label")
            yield Static("", id="file-count")
            yield Static("", id="file-list")
            yield Static("", classes="hline")
            yield Static("❯ COMMIT MESSAGE", classes="section-label")
            yield Static("", id="commit-list")
            yield Static("", id="spinner-line")
            yield Static("", classes="hline")
            yield Static("", id="buttons")

        def on_mount(self) -> None:
            self._render_all()

        def _render_all(self) -> None:
            self._render_header()
            self._render_files()
            self._render_commit()
            self._render_buttons()

        def _render_header(self) -> None:
            self.query_one("#header", Static).update(
                "[" + ACCENT + "]◆[/" + ACCENT + "] [bold white]ai-commit[/bold white]          [" + TEXT_MID + "]branch: " + self.branch + "[/" + TEXT_MID + "]"
            )

        def _render_files(self) -> None:
            count = self.query_one("#file-count", Static)
            files = self.query_one("#file-list", Static)
            
            if not self.staged_files:
                count.update("[" + ERROR + "]no staged changes — run git add first[/" + ERROR + "]")
                files.update("")
                return
            
            count.update("[" + TEXT_LIGHT + "]" + str(len(self.staged_files)) + " files staged[/" + TEXT_LIGHT + "]")
            
            files_to_show = self.staged_files[:5]
            remaining = len(self.staged_files) - 5
            
            lines = []
            for f in files_to_show:
                parts = f.split("/")
                short_path = "/".join(parts[-2:]) if len(parts) >= 2 else f
                lines.append("[" + ACCENT + "]●[/" + ACCENT + "] " + short_path)
            
            if remaining > 0:
                lines.append("[" + TEXT_LIGHT + "]+ " + str(remaining) + " more files[/" + TEXT_LIGHT + "]")
            
            files.update("\n".join(lines))

        def _render_commit(self) -> None:
            commit = self.query_one("#commit-list", Static)
            if self.commit_message:
                commit.update("[" + ACCENT + " bold]" + self.commit_message + "[/" + ACCENT + " bold]")
            else:
                commit.update("[" + TEXT_DIM + " italic]waiting for generation —[/" + TEXT_DIM + " italic]")

        def _render_buttons(self) -> None:
            btns = self.query_one("#buttons", Static)
            parts = []
            for i, label in enumerate(self.button_labels):
                key = ["g", "a", "c", "q"][i]
                disabled = getattr(self, 'committing', False) or getattr(self, 'generating', False)
                if i == self.selected and not disabled:
                    parts.append("[" + ACCENT + " bold][" + key + "] " + label + "[/" + ACCENT + " bold]")
                elif disabled:
                    parts.append("[" + TEXT_DIM + "] " + key + "  " + label + "  [/" + TEXT_DIM + "]")
                else:
                    parts.append("[" + TEXT_MID + "] " + key + "  " + label + "  [/" + TEXT_MID + "]")
            btns.update("  " + "  ".join(parts))

        def _start_spinner(self, message: str, use_color: bool = True) -> None:
            self.committing = True
            self.generating = True
            self.spinner_char_index = 0
            self.current_spinner_message = message
            self._render_buttons()
            self.spinner_timer = self.set_interval(0.1, lambda: self._update_spinner(use_color))

        def _update_spinner(self, use_color: bool = True) -> None:
            spinner_char = SPINNER_CHARS[self.spinner_char_index % len(SPINNER_CHARS)]
            color_tag = f"[{ACCENT}]{spinner_char}[/{ACCENT}] " if use_color else f"{spinner_char} "
            self.query_one("#spinner-line", Static).update(f"{color_tag}{self.current_spinner_message}")
            self.spinner_char_index += 1

        def _stop_spinner(self, final_message: str, color: str) -> None:
            if self.spinner_timer:
                self.spinner_timer.stop()
                self.spinner_timer = None
            self.query_one("#spinner-line", Static).update(f"[{color}]{final_message}[/{color}]")
            self.committing = False
            self.generating = False
            self._render_buttons()
            self.call_later(lambda _: self.query_one("#spinner-line", Static).update(""), 3)

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
            self.current_spinner_message = random.choice(SPINNER_MESSAGES)
            self._start_spinner(self.current_spinner_message, use_color=False)

            def worker():
                msg = call_gemini_api(self.diff, self.api_key)
                self.call_later(self._on_generated, msg)

            threading.Thread(target=worker, daemon=True).start()

        def _on_generated(self, message: str) -> None:
            if self.spinner_timer:
                self.spinner_timer.stop()
                self.spinner_timer = None

            if message and not message.startswith("ERROR:"):
                self.commit_message = message
                self.query_one("#spinner-line", Static).update("")
            else:
                self.commit_message = ""
                if message and "429" in message:
                    self.query_one("#spinner-line", Static).update("[" + ERROR + "]rate limit exceeded — try again later[/" + ERROR + "]")
                else:
                    error_msg = message.replace("ERROR: ", "") if message else "failed to generate message"
                    self.query_one("#spinner-line", Static).update("[" + ERROR + "]" + error_msg + "[/" + ERROR + "]")

            self._render_commit()
            self.generating = False
            self.committing = False
            self._render_buttons()

        def action_apply(self) -> None:
            if not self.commit_message:
                self.query_one("#spinner-line", Static).update("[" + ERROR + "]no message to commit[/" + ERROR + "]")
                self.call_later(lambda _: self.query_one("#spinner-line", Static).update(""), 2)
                return

            self._start_spinner("Committing...", use_color=True)
            
            def worker():
                success = apply_git_commit(self.commit_message, self.path)
                if success:
                    self.call_later(self._on_commit_success)
                else:
                    self.call_later(self._on_commit_failure)
            
            threading.Thread(target=worker, daemon=True).start()

        def _on_commit_success(self) -> None:
            if self.spinner_timer:
                self.spinner_timer.stop()
                self.spinner_timer = None
            self.query_one("#spinner-line", Static).update("[" + SUCCESS + "]✓ Committed successfully[/" + SUCCESS + "]")
            self.committing = False
            self._render_buttons()
            self.call_later(self.exit, 3)

        def _on_commit_failure(self) -> None:
            if self.spinner_timer:
                self.spinner_timer.stop()
                self.spinner_timer = None
            self.query_one("#spinner-line", Static).update("[" + ERROR + "]✗ Commit failed — check git status[/" + ERROR + "]")
            self.committing = False
            self._render_buttons()
            self.call_later(lambda _: self.query_one("#spinner-line", Static).update(""), 3)

        def action_copy(self) -> None:
            if not self.commit_message:
                self.query_one("#spinner-line", Static).update("[" + ERROR + "]no message to copy[/" + ERROR + "]")
                self.call_later(lambda _: self.query_one("#spinner-line", Static).update(""), 2)
                return

            if PYPERCLIP_AVAILABLE:
                pyperclip.copy(self.commit_message)
                self.query_one("#spinner-line", Static).update("[" + SUCCESS + "]✓ copied to clipboard[/" + SUCCESS + "]")
            else:
                self.query_one("#spinner-line", Static).update("[" + ERROR + "]pyperclip not available[/" + ERROR + "]")

            self.call_later(lambda _: self.query_one("#spinner-line", Static).update(""), 2)

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
            print("Error: textual not installed")
            sys.exit(1)
        return

    commit_message = call_gemini_api(diff, api_key)
    print(commit_message)

    if args.apply:
        apply_git_commit(commit_message, args.dir)


if __name__ == "__main__":
    main()