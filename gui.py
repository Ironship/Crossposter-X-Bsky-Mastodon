#!/usr/bin/env python3
"""GUI for Crossposter X-Bsky-Mastodon

Provides a graphical interface for configuring credentials and settings,
running the crossposter manually, and viewing live log output.

Run with:  python gui.py
"""

import os
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

# Absolute path to the project root (same directory as this file)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUTH_FILE = os.path.join(BASE_DIR, "settings", "auth.py")
SETTINGS_FILE = os.path.join(BASE_DIR, "settings", "settings.py")
CROSSPOST_SCRIPT = os.path.join(BASE_DIR, "crosspost.py")


# ---------------------------------------------------------------------------
# Helpers: read / write Python source files
# ---------------------------------------------------------------------------

def _read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _write_file(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def read_py_string(content: str, var_name: str) -> str:
    """Return the *first* double- or single-quoted string assigned to *var_name*."""
    for quote in ('"', "'"):
        m = re.search(rf'{var_name}\s*=\s*{quote}([^{quote}]*){quote}', content)
        if m:
            return m.group(1)
    return ""


def read_py_bool(content: str, var_name: str) -> bool:
    """Return the first boolean value assigned to *var_name*."""
    m = re.search(rf'{var_name}\s*=\s*(True|False)', content)
    return m.group(1) == "True" if m else False


def read_py_int(content: str, var_name: str) -> int:
    """Return the first integer value assigned to *var_name* (handles multiline)."""
    # Single-line: var = 123
    m = re.search(rf'{var_name}\s*=\s*(\d+)', content)
    if m:
        return int(m.group(1))
    # Multiline: var = (\n    123\n)
    m = re.search(rf'{var_name}\s*=\s*\(\s*(\d+)', content)
    if m:
        return int(m.group(1))
    return 0


def write_py_string(content: str, var_name: str, value: str) -> str:
    """Replace the first quoted string assignment for *var_name*."""
    for quote in ('"', "'"):
        new, n = re.subn(
            rf'({var_name}\s*=\s*){quote}[^{quote}]*{quote}',
            rf'\g<1>"{value}"',
            content,
            count=1,
        )
        if n:
            return new
    return content


def write_py_bool(content: str, var_name: str, value: bool) -> str:
    """Replace the first boolean assignment for *var_name*."""
    new_val = "True" if value else "False"
    new, _ = re.subn(
        rf'({var_name}\s*=\s*)(True|False)',
        rf'\g<1>{new_val}',
        content,
        count=1,
    )
    return new


def write_py_int(content: str, var_name: str, value: int) -> str:
    """Replace the first integer assignment for *var_name*."""
    new, _ = re.subn(
        rf'({var_name}\s*=\s*)\d+',
        rf'\g<1>{value}',
        content,
        count=1,
    )
    return new


# ---------------------------------------------------------------------------
# Main GUI class
# ---------------------------------------------------------------------------

class CrossposterGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Crossposter X-Bsky-Mastodon")
        self.root.geometry("860x680")
        self.root.minsize(700, 520)

        # State
        self._run_process: subprocess.Popen | None = None
        self._stop_auto_run = threading.Event()
        self._auto_run_thread: threading.Thread | None = None
        self.auto_run_var = tk.BooleanVar(value=False)
        self.interval_var = tk.IntVar(value=3600)

        # Build UI
        notebook = ttk.Notebook(root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.notebook = notebook

        self._auth_tab = ttk.Frame(notebook)
        notebook.add(self._auth_tab, text="  Authentication  ")

        self._settings_tab = ttk.Frame(notebook)
        notebook.add(self._settings_tab, text="  Settings  ")

        self._run_tab = ttk.Frame(notebook)
        notebook.add(self._run_tab, text="  Run & Logs  ")

        self._build_auth_tab()
        self._build_settings_tab()
        self._build_run_tab()

        # Load persisted values
        self._load_auth()
        self._load_settings()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # Authentication tab
    # ------------------------------------------------------------------

    def _build_auth_tab(self) -> None:
        outer = ttk.Frame(self._auth_tab)
        outer.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        ttk.Label(outer, text="Authentication Settings", font=(None, 13, "bold")).grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 12)
        )

        self._auth_vars: dict[str, tk.StringVar] = {}
        row = 1

        def _section(title: str) -> None:
            nonlocal row
            ttk.Label(outer, text=title, font=(None, 10, "bold")).grid(
                row=row, column=0, columnspan=2, sticky=tk.W, pady=(10, 2)
            )
            row += 1

        def _field(label: str, key: str, masked: bool = False) -> None:
            nonlocal row
            ttk.Label(outer, text=label).grid(
                row=row, column=0, sticky=tk.W, padx=(20, 6), pady=2
            )
            var = tk.StringVar()
            self._auth_vars[key] = var
            ttk.Entry(
                outer, textvariable=var, width=48, show="●" if masked else ""
            ).grid(row=row, column=1, sticky=tk.EW, pady=2)
            row += 1

        _section("Bluesky")
        _field("Handle (e.g. user.bsky.social):", "BSKY_HANDLE")
        _field("App Password:", "BSKY_PASSWORD", masked=True)

        _section("Mastodon")
        _field("Handle (e.g. user@mastodon.social):", "MASTODON_HANDLE")
        _field("Instance URL (e.g. https://mastodon.social):", "MASTODON_INSTANCE")
        _field("Access Token:", "MASTODON_TOKEN", masked=True)

        _section("Twitter / X")
        _field("App Key:", "TWITTER_APP_KEY", masked=True)
        _field("App Secret:", "TWITTER_APP_SECRET", masked=True)
        _field("Access Token:", "TWITTER_ACCESS_TOKEN", masked=True)
        _field("Access Token Secret:", "TWITTER_ACCESS_TOKEN_SECRET", masked=True)

        ttk.Button(
            outer, text="💾  Save Authentication", command=self._save_auth
        ).grid(row=row, column=0, columnspan=2, pady=16)

        outer.columnconfigure(1, weight=1)

    # ------------------------------------------------------------------
    # Settings tab
    # ------------------------------------------------------------------

    def _build_settings_tab(self) -> None:
        # Wrap in a canvas so it scrolls on small screens
        canvas = tk.Canvas(self._settings_tab, highlightthickness=0)
        vsb = ttk.Scrollbar(self._settings_tab, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner = ttk.Frame(canvas)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_frame_configure(event: tk.Event) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event: tk.Event) -> None:
            canvas.itemconfig(win_id, width=event.width)

        inner.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        # Mousewheel scrolling
        def _on_mousewheel(event: tk.Event) -> None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        frame = ttk.Frame(inner, padding="15 15 15 15")
        frame.pack(fill=tk.BOTH, expand=True)

        self._settings_vars: dict[str, tk.Variable] = {}
        row = 0

        ttk.Label(frame, text="Application Settings", font=(None, 13, "bold")).grid(
            row=row, column=0, columnspan=3, sticky=tk.W, pady=(0, 12)
        )
        row += 1

        def _section(title: str) -> None:
            nonlocal row
            ttk.Separator(frame, orient="horizontal").grid(
                row=row, column=0, columnspan=3, sticky=tk.EW, pady=(10, 2)
            )
            row += 1
            ttk.Label(frame, text=title, font=(None, 10, "bold")).grid(
                row=row, column=0, columnspan=3, sticky=tk.W
            )
            row += 1

        def _check(label: str, key: str) -> None:
            nonlocal row
            var = tk.BooleanVar()
            self._settings_vars[key] = var
            ttk.Checkbutton(frame, text=label, variable=var).grid(
                row=row, column=0, columnspan=2, sticky=tk.W, padx=(20, 6), pady=2
            )
            row += 1

        def _combo(label: str, key: str, choices: list[str], width: int = 18) -> None:
            nonlocal row
            ttk.Label(frame, text=label).grid(
                row=row, column=0, sticky=tk.W, padx=(20, 6), pady=2
            )
            var = tk.StringVar()
            self._settings_vars[key] = var
            ttk.Combobox(
                frame, textvariable=var, values=choices, width=width, state="readonly"
            ).grid(row=row, column=1, sticky=tk.W, pady=2)
            row += 1

        def _spin(label: str, key: str, lo: int = 0, hi: int = 99_999) -> None:
            nonlocal row
            ttk.Label(frame, text=label).grid(
                row=row, column=0, sticky=tk.W, padx=(20, 6), pady=2
            )
            var = tk.IntVar()
            self._settings_vars[key] = var
            ttk.Spinbox(frame, textvariable=var, from_=lo, to=hi, width=10).grid(
                row=row, column=1, sticky=tk.W, pady=2
            )
            row += 1

        # ── Platforms ──────────────────────────────────────────────────
        _section("Platforms")
        _check("Enable Twitter / X crossposting", "Twitter")
        _check("Enable Mastodon crossposting", "Mastodon")

        # ── Posting behaviour ──────────────────────────────────────────
        _section("Posting Behaviour")
        _combo(
            "Log Level:",
            "log_level",
            ["DEBUG", "INFO", "WARNING", "ERROR"],
        )
        _combo(
            "Mastodon Visibility:",
            "visibility",
            ["public", "unlisted", "private", "hybrid"],
        )
        _combo(
            "Mentions Handling:",
            "mentions",
            ["ignore", "skip", "strip", "url"],
        )
        _check("Post by default (crosspost unless a toggle tag says otherwise)", "post_default")
        _check("Crosspost quote posts (adds link for posts not in your own thread)", "quote_posts")
        _check(
            "Cross-delete (delete on platforms when deleted on Bluesky within 1 hour)",
            "cross_delete",
        )

        # ── Limits ─────────────────────────────────────────────────────
        _section("Limits & Advanced")
        _spin("Max retries on failure:", "max_retries", lo=1)
        _spin("Post time limit (hours):", "post_time_limit", lo=1)
        _spin("Max posts per hour (0 = unlimited):", "max_per_hour")
        _spin("Rate-limit buffer (%):", "rate_limit_buffer", lo=0, hi=100)
        _spin("Max tweet length (280 or 4000 for Blue):", "max_tweet_length", lo=1)
        _combo("Overflow posts:", "overflow_posts", ["retry", "skip"], width=10)

        ttk.Button(
            frame, text="💾  Save Settings", command=self._save_settings
        ).grid(row=row, column=0, columnspan=2, pady=16)

    # ------------------------------------------------------------------
    # Run & Logs tab
    # ------------------------------------------------------------------

    def _build_run_tab(self) -> None:
        frame = ttk.Frame(self._run_tab, padding="10 10 10 10")
        frame.pack(fill=tk.BOTH, expand=True)

        # ── Controls ───────────────────────────────────────────────────
        ctrl = ttk.LabelFrame(frame, text="Controls", padding="8 6 8 6")
        ctrl.pack(fill=tk.X, pady=(0, 8))

        btn_row = ttk.Frame(ctrl)
        btn_row.pack(fill=tk.X)

        self._run_btn = ttk.Button(
            btn_row, text="▶  Run Now", command=self.run_now, width=14
        )
        self._run_btn.pack(side=tk.LEFT, padx=(0, 8))

        self._stop_btn = ttk.Button(
            btn_row, text="■  Stop", command=self._stop_run, width=10, state=tk.DISABLED
        )
        self._stop_btn.pack(side=tk.LEFT, padx=(0, 18))

        auto_row = ttk.Frame(ctrl)
        auto_row.pack(fill=tk.X, pady=(6, 0))

        ttk.Checkbutton(
            auto_row,
            text="Auto-run every",
            variable=self.auto_run_var,
            command=self._toggle_auto_run,
        ).pack(side=tk.LEFT)

        self._interval_spin = ttk.Spinbox(
            auto_row, textvariable=self.interval_var, from_=60, to=86400, width=8
        )
        self._interval_spin.pack(side=tk.LEFT, padx=4)
        ttk.Label(auto_row, text="seconds").pack(side=tk.LEFT)

        self._status_var = tk.StringVar(value="Ready")
        ttk.Label(ctrl, textvariable=self._status_var, foreground="gray").pack(
            anchor=tk.W, pady=(4, 0)
        )

        # ── Log area ───────────────────────────────────────────────────
        log_frame = ttk.LabelFrame(frame, text="Log Output", padding="5 5 5 5")
        log_frame.pack(fill=tk.BOTH, expand=True)

        toolbar = ttk.Frame(log_frame)
        toolbar.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(toolbar, text="🗑  Clear", command=self._clear_log).pack(side=tk.LEFT)

        self._log = scrolledtext.ScrolledText(
            log_frame, height=18, state=tk.DISABLED, font=("Courier", 9), wrap=tk.WORD
        )
        self._log.pack(fill=tk.BOTH, expand=True)

        # Colour tags
        self._log.tag_config("ERROR", foreground="#cc0000")
        self._log.tag_config("WARNING", foreground="#cc7700")
        self._log.tag_config("SUCCESS", foreground="#007700")
        self._log.tag_config("INFO", foreground="#004488")
        self._log.tag_config("DEBUG", foreground="#888888")
        self._log.tag_config("META", foreground="#555555")

    # ------------------------------------------------------------------
    # Load / save helpers
    # ------------------------------------------------------------------

    def _load_auth(self) -> None:
        try:
            content = _read_file(AUTH_FILE)
            for key in self._auth_vars:
                value = read_py_string(content, key)
                if value and not value.startswith("your_"):
                    self._auth_vars[key].set(value)
        except Exception as exc:
            self._log_line(f"[WARNING] Could not load auth settings: {exc}", "WARNING")

    def _save_auth(self) -> None:
        try:
            content = _read_file(AUTH_FILE)
            for key, var in self._auth_vars.items():
                value = var.get().strip()
                if value:
                    content = write_py_string(content, key, value)
            _write_file(AUTH_FILE, content)
            messagebox.showinfo(
                "Saved", "Authentication settings saved to settings/auth.py"
            )
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to save authentication:\n{exc}")

    def _load_settings(self) -> None:
        try:
            content = _read_file(SETTINGS_FILE)
            bool_keys = {"Twitter", "Mastodon", "post_default", "quote_posts", "cross_delete"}
            int_keys = {
                "max_retries", "post_time_limit", "max_per_hour",
                "rate_limit_buffer", "max_tweet_length",
            }
            str_keys = {"log_level", "visibility", "mentions", "overflow_posts"}

            for key in bool_keys:
                if key in self._settings_vars:
                    self._settings_vars[key].set(read_py_bool(content, key))
            for key in int_keys:
                if key in self._settings_vars:
                    self._settings_vars[key].set(read_py_int(content, key))
            for key in str_keys:
                if key in self._settings_vars:
                    v = read_py_string(content, key)
                    if v:
                        self._settings_vars[key].set(v)
        except Exception as exc:
            self._log_line(f"[WARNING] Could not load settings: {exc}", "WARNING")

    def _save_settings(self) -> None:
        try:
            content = _read_file(SETTINGS_FILE)
            bool_keys = {"Twitter", "Mastodon", "post_default", "quote_posts", "cross_delete"}
            int_keys = {
                "max_retries", "post_time_limit", "max_per_hour",
                "rate_limit_buffer", "max_tweet_length",
            }
            str_keys = {"log_level", "visibility", "mentions", "overflow_posts"}

            for key in bool_keys:
                if key in self._settings_vars:
                    content = write_py_bool(content, key, self._settings_vars[key].get())
            for key in int_keys:
                if key in self._settings_vars:
                    content = write_py_int(content, key, int(self._settings_vars[key].get()))
            for key in str_keys:
                if key in self._settings_vars:
                    content = write_py_string(
                        content, key, str(self._settings_vars[key].get())
                    )
            _write_file(SETTINGS_FILE, content)
            messagebox.showinfo("Saved", "Settings saved to settings/settings.py")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to save settings:\n{exc}")

    # ------------------------------------------------------------------
    # Log helpers
    # ------------------------------------------------------------------

    def _log_line(self, line: str, tag: str = "INFO") -> None:
        """Append *line* to the log widget (thread-safe via after())."""
        self._log.config(state=tk.NORMAL)
        self._log.insert(tk.END, line + "\n", tag)
        self._log.see(tk.END)
        self._log.config(state=tk.DISABLED)

    def _append_log(self, line: str) -> None:
        """Determine tag from line content and append to log."""
        low = line.lower()
        if "[error]" in low:
            tag = "ERROR"
        elif "[warning]" in low or "[warn]" in low:
            tag = "WARNING"
        elif "[debug]" in low:
            tag = "DEBUG"
        elif "[success]" in low:
            tag = "SUCCESS"
        else:
            tag = "INFO"
        self._log_line(line, tag)

    def _clear_log(self) -> None:
        self._log.config(state=tk.NORMAL)
        self._log.delete("1.0", tk.END)
        self._log.config(state=tk.DISABLED)

    def _set_status(self, text: str, colour: str = "gray") -> None:
        self._status_var.set(text)

    # ------------------------------------------------------------------
    # Running the crossposter
    # ------------------------------------------------------------------

    def run_now(self) -> None:
        """Spawn crosspost.py in a background thread."""
        if self._run_process and self._run_process.poll() is None:
            messagebox.showwarning("Running", "The crossposter is already running.")
            return

        self.notebook.select(2)  # switch to Run & Logs tab
        self._run_btn.config(state=tk.DISABLED)
        self._stop_btn.config(state=tk.NORMAL)
        self._status_var.set("Running…")

        thread = threading.Thread(target=self._run_worker, daemon=True)
        thread.start()

    def _run_worker(self) -> None:
        try:
            self.root.after(0, self._log_line, "─" * 60, "META")
            self.root.after(
                0,
                self._log_line,
                f"Starting crosspost run at {time.strftime('%Y-%m-%d %H:%M:%S')}",
                "META",
            )

            self._run_process = subprocess.Popen(
                [sys.executable, CROSSPOST_SCRIPT],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=BASE_DIR,
                bufsize=1,
            )

            assert self._run_process.stdout is not None
            for raw_line in iter(self._run_process.stdout.readline, ""):
                stripped = raw_line.rstrip()
                if stripped:
                    self.root.after(0, self._append_log, stripped)

            self._run_process.wait()
            code = self._run_process.returncode

            if code == 0:
                self.root.after(0, self._log_line, "✔ Run completed successfully.", "SUCCESS")
                self.root.after(0, self._status_var.set, "Completed ✔")
            else:
                self.root.after(
                    0,
                    self._log_line,
                    f"✘ Run failed (exit code {code}).",
                    "ERROR",
                )
                self.root.after(0, self._status_var.set, f"Failed (exit code {code})")

        except Exception as exc:
            self.root.after(0, self._log_line, f"Error: {exc}", "ERROR")
            self.root.after(0, self._status_var.set, "Error")
        finally:
            self.root.after(0, self._run_btn.config, {"state": tk.NORMAL})
            self.root.after(0, self._stop_btn.config, {"state": tk.DISABLED})

    def _stop_run(self) -> None:
        if self._run_process and self._run_process.poll() is None:
            self._run_process.terminate()
            self._log_line("■ Run stopped by user.", "WARNING")
            self._status_var.set("Stopped")
        self._run_btn.config(state=tk.NORMAL)
        self._stop_btn.config(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # Auto-run
    # ------------------------------------------------------------------

    def _toggle_auto_run(self) -> None:
        if self.auto_run_var.get():
            self._stop_auto_run.clear()
            self._auto_run_thread = threading.Thread(
                target=self._auto_run_loop, daemon=True
            )
            self._auto_run_thread.start()
            self._log_line(
                f"Auto-run enabled (every {self.interval_var.get()} s).", "META"
            )
        else:
            self._stop_auto_run.set()
            self._log_line("Auto-run disabled.", "META")

    def _auto_run_loop(self) -> None:
        while not self._stop_auto_run.is_set():
            self.root.after(0, self.run_now)
            # Wait for the subprocess to finish before counting down
            if self._run_process:
                self._run_process.wait()
            interval = self.interval_var.get()
            for _ in range(interval):
                if self._stop_auto_run.is_set():
                    return
                time.sleep(1)

    # ------------------------------------------------------------------
    # Window close
    # ------------------------------------------------------------------

    def _on_close(self) -> None:
        if self._run_process and self._run_process.poll() is None:
            if not messagebox.askokcancel(
                "Quit",
                "The crossposter is currently running.\nStop it and quit?",
            ):
                return
            self._run_process.terminate()
        self._stop_auto_run.set()
        self.root.destroy()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    root = tk.Tk()
    # Use a modern theme if available
    style = ttk.Style(root)
    for theme in ("clam", "alt", "default"):
        if theme in style.theme_names():
            style.theme_use(theme)
            break

    CrossposterGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
