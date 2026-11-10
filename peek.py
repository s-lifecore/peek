#!/usr/bin/env python3
"""peek - GUI file viewer for WSL / Linux / macOS terminals"""

import sys
import os
import re
import json
import shutil
import secrets
import subprocess
import threading
import time
import socket
import difflib
from pathlib import Path

SUPPORTED_EXT = {'.md', '.markdown', '.txt', '.pdf'}
VERSION = "1.14.1"
MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB

CONFIG_FILE = Path.home() / ".config" / "peek" / "settings.json"

DEFAULT_SETTINGS = {
    "theme": "catppuccin-mocha",
    "custom_colors": {
        "bg": "#1e1e2e", "surface": "#181825", "overlay": "#313244",
        "text": "#cdd6f4", "muted": "#6c7086", "accent": "#89b4fa",
    },
    "quit_key": "ctrl+q",
    "save_key": "ctrl+s",
}

THEMES = {
    "catppuccin-mocha": {
        "bg": "#1e1e2e", "surface": "#181825", "overlay": "#313244",
        "text": "#cdd6f4", "muted": "#6c7086", "accent": "#89b4fa",
    },
    "catppuccin-latte": {
        "bg": "#eff1f5", "surface": "#e6e9ef", "overlay": "#ccd0da",
        "text": "#4c4f69", "muted": "#9ca0b0", "accent": "#1e66f5",
    },
    "nord": {
        "bg": "#2e3440", "surface": "#3b4252", "overlay": "#434c5e",
        "text": "#eceff4", "muted": "#4c566a", "accent": "#88c0d0",
    },
    "gruvbox-dark": {
        "bg": "#282828", "surface": "#3c3836", "overlay": "#504945",
        "text": "#ebdbb2", "muted": "#665c54", "accent": "#83a598",
    },
    "tokyo-night": {
        "bg": "#1a1b26", "surface": "#16161e", "overlay": "#2f3549",
        "text": "#c0caf5", "muted": "#565f89", "accent": "#7aa2f7",
    },
}

HELP_EN = """peek {version} - GUI file viewer for WSL / Linux / macOS terminals

USAGE:
  peek [options] <file>

OPTIONS:
  -t, --tui             Open in TUI mode directly in the terminal
  -b, --browser         Open in browser with auto-detected platform (default)
  -w, --windows         Browser: Windows default browser, save to Windows
  -l, --linux           Browser: Linux default browser, save to ~/Downloads/
  -m, --mac             Browser: macOS default browser, save to ~/Downloads/
  -e, --edit            Edit mode: browser live editor (detached server) or TUI editor with -t
  -s, --settings        Open TUI settings (theme, colors, keybindings) — standalone flag
  --update              Pull latest version from git and reinstall deps
  --help-en             Show this help (English)
  --help-ja             Show help in Japanese
  --version             Show version

SUPPORTED FILE TYPES:
  .md / .markdown       Rendered Markdown with syntax highlighting
  .txt                  Plain text with line numbers
  .pdf                  Browser: native viewer / TUI: text via pdftotext

EXAMPLES:
  peek README.md             # browser (default, platform auto-detected)
  peek -t README.md          # TUI viewer
  peek -t -e README.md       # TUI editor with live preview (Ctrl+S: save, Ctrl+Q: quit)
  peek -w README.md          # Windows browser
  peek -l notes.txt          # Linux browser
  peek -m README.md          # macOS browser
  peek -e README.md          # browser live editor

HOW IT WORKS:
  Browser mode (default): starts a local Flask server and opens the browser.
  TUI mode (-t): renders the file directly in the terminal using textual.
  With -e, server runs in background and terminal is freed (kill <PID> to stop).
""".format(version=VERSION)

HELP_JA = """peek {version} - WSL / Linux / macOS ターミナル用 GUI ファイルビューア

使い方:
  peek [オプション] <ファイル>

オプション:
  -t, --tui             ターミナル内 TUI モードで表示
  -b, --browser         ブラウザで開く（デフォルト・OS 自動検出）
  -w, --windows         ブラウザ: Windows のデフォルトブラウザ・Windows に保存
  -l, --linux           ブラウザ: Linux のデフォルトブラウザ・~/Downloads/ に保存
  -m, --mac             ブラウザ: macOS のデフォルトブラウザ・~/Downloads/ に保存
  -e, --edit            編集モード: ブラウザライブエディタ（バックグラウンド）/ -t と組み合わせて TUI エディタ
  -s, --settings        TUI 設定画面を開く（テーマ・カラー・キーバインド）— 単独フラグ
  --update              git から最新版を取得して依存関係を更新
  --help-en             英語のヘルプを表示
  --help-ja             このヘルプを表示（日本語）
  --version             バージョンを表示

対応ファイル形式:
  .md / .markdown        シンタックスハイライト付き Markdown レンダリング
  .txt                   行番号付きプレーンテキスト表示
  .pdf                   ブラウザ: ネイティブビューア / TUI: pdftotext でテキスト抽出

使用例:
  peek README.md             # ブラウザで開く（デフォルト・OS 自動検出）
  peek -t README.md          # TUI ビューア
  peek -t -e README.md       # TUI エディタ（リアルタイムプレビュー / Ctrl+S: 保存 / Ctrl+Q: 終了）
  peek -w README.md          # Windows ブラウザ
  peek -l notes.txt          # Linux ブラウザ
  peek -m README.md          # macOS ブラウザ
  peek -e README.md          # ブラウザライブエディタ

仕組み:
  ブラウザモード（デフォルト）: Flask ローカルサーバーを起動しブラウザで開く。
  TUI モード (-t): textual を使ってターミナル内に直接レンダリング。
  -e: サーバーがバックグラウンドで動作し、端末が解放されます（kill <PID> で停止）。
""".format(version=VERSION)


def find_free_port(start=8899):
    for port in range(start, start + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free port available in range 8899-8999")


def _detect_default_platform():
    if sys.platform == "darwin":
        return "mac"
    try:
        with open("/proc/version") as f:
            if "microsoft" in f.read().lower():
                return "windows"
    except OSError:
        pass
    return "linux"


def open_browser(port, token, platform="windows"):
    time.sleep(0.8)
    url = f"http://localhost:{port}/?token={token}"

    if platform == "mac":
        cmds = [["open", url]]
    elif platform == "linux":
        cmds = [
            ["xdg-open", url],
            ["firefox", url],
            ["google-chrome", url],
            ["chromium-browser", url],
            ["chromium", url],
        ]
    else:
        cmds = [
            ["cmd.exe", "/c", "start", "", url],
            ["wslview", url],
        ]

    for cmd in cmds:
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except FileNotFoundError:
            continue

    # All commands failed — print platform-specific guidance
    if platform == "mac":
        print("peek: macOS のブラウザを開けませんでした。")
        print("      `open` コマンドが使えるか確認してください。")
        print(f"      または手動でアクセス: {url}")
    elif platform == "linux":
        print("peek: Linux のブラウザが見つかりませんでした。")
        print("      以下のいずれかでインストールしてください:")
        print("        sudo apt install firefox")
        print("        sudo apt install chromium-browser")
        print(f"      または手動でアクセス: {url}")
    else:
        print("peek: Windows のブラウザを開けませんでした。")
        print("      WSL から cmd.exe が実行できるか確認してください。")
        print("      Linux ブラウザで開く場合: peek -l <ファイル>")
        print(f"      または手動でアクセス: {url}")


def _sanitize_error(msg):
    home = os.path.expanduser("~")
    return msg.replace(home, "~") if home != "~" else msg


def _local_save(src_path, filename=None, downloads_dir=None):
    """Copy src_path to downloads_dir (default ~/Downloads/), return destination path string."""
    if downloads_dir is None:
        downloads_dir = Path.home() / "Downloads"
    downloads_dir = Path(downloads_dir)
    downloads_dir.mkdir(parents=True, exist_ok=True)
    dest = downloads_dir / (filename or Path(src_path).name)
    shutil.copy2(str(src_path), str(dest))
    return str(dest)


def _windows_downloads_path():
    """Return Windows Downloads folder as a WSL-accessible Path, or None."""
    win_profile = None
    for cmd, enc in (
        (['wslvar', 'USERPROFILE'], 'utf-8'),
        (['cmd.exe', '/c', 'echo', '%USERPROFILE%'], 'cp932'),
    ):
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=5)
            if r.returncode == 0 and r.stdout.strip():
                win_profile = r.stdout.decode(enc, errors='replace').strip().replace('\r', '').replace('\n', '')
                break
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    if not win_profile or ':\\' not in win_profile:
        return None
    drive, rest = win_profile.split(':\\', 1)
    p = Path(f"/mnt/{drive.lower()}/{rest.replace(chr(92), '/')}/Downloads")
    return p if p.exists() else None


def _normalize_path(path_str):
    """Convert Windows-style path (C:\\...) to WSL path (/mnt/c/...), expand ~."""
    p = path_str.strip()
    if len(p) >= 3 and p[1] == ':' and p[2] in ('\\', '/'):
        drive = p[0].lower()
        rest = p[3:].replace('\\', '/')
        return f"/mnt/{drive}/{rest}"
    return p.replace('\\', '/')


def _default_save_display(platform, win_downloads, filename):
    """Return the default save path as a display string for the Save As dialog."""
    if platform == "windows" and win_downloads:
        # Convert WSL /mnt/c/... back to C:\... for display
        parts = str(win_downloads).lstrip('/').split('/')
        # ['mnt', 'c', 'Users', 'straw', 'Downloads']
        drive = parts[1].upper()
        rest = '\\'.join(parts[2:])
        return f"{drive}:\\{rest}\\{filename}"
    downloads = Path.home() / "Downloads" / filename
    return str(downloads)


# Compiled once at import time for performance
_RE_DANGEROUS_TAG = re.compile(
    r'<\s*(?:script|style|iframe|object|embed|form|base|link|meta)'
    r'(?:\s[^>]*)?>.*?</\s*(?:script|style|iframe|object|embed|form|base|link|meta)\s*>'
    r'|<\s*(?:script|style|iframe|object|embed|form|base|link|meta)(?:\s[^>]*)?/?>',
    re.DOTALL | re.IGNORECASE,
)
_RE_EVENT_HANDLER = re.compile(r'\s+on\w+\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s>]+)', re.IGNORECASE)
_RE_JS_URL = re.compile(r'(href|src|action)\s*=\s*["\']?\s*javascript:', re.IGNORECASE)


def _sanitize_html(html):
    """Strip dangerous tags, event handlers, and javascript: URLs from HTML."""
    html = _RE_DANGEROUS_TAG.sub('', html)
    html = _RE_EVENT_HANDLER.sub('', html)
    html = _RE_JS_URL.sub(r'\1="#"', html)
    return html


def _make_restricted_fetcher(allowed_dir):
    """Return a weasyprint URL fetcher that blocks file:// outside allowed_dir."""
    from weasyprint import URLFetcher
    allowed = os.path.realpath(allowed_dir)

    class RestrictedFetcher(URLFetcher):
        def __call__(self, url, **kwargs):
            if url.startswith("file://"):
                raw = url[len("file://"):]
                real = os.path.realpath(raw)
                if real != allowed and not real.startswith(allowed + os.sep):
                    raise ValueError("Access denied: path outside allowed directory")
            return super().__call__(url, **kwargs)

    return RestrictedFetcher()


PRINT_CSS = """
body {
    font-family: "Hiragino Sans", "Yu Gothic", "Noto Sans CJK JP", sans-serif;
    font-size: 11pt;
    line-height: 1.8;
    color: #1a1a1a;
    max-width: 740px;
    margin: 0 auto;
    padding: 0 1cm;
}
h1, h2, h3, h4 { color: #111; line-height: 1.3; margin-top: 1.5em; margin-bottom: 0.5em; }
h1 { font-size: 1.9em; border-bottom: 2px solid #ddd; padding-bottom: 0.3em; margin-top: 0; }
h2 { font-size: 1.45em; border-bottom: 1px solid #eee; padding-bottom: 0.2em; }
h3 { font-size: 1.2em; }
p  { margin: 0.9em 0; }
ul, ol { padding-left: 1.8em; margin: 0.5em 0; }
li { margin: 0.25em 0; }
a  { color: #0969da; }
code {
    background: #f4f4f5; padding: 0.15em 0.4em;
    border-radius: 4px;
    font-family: "Consolas", "JetBrains Mono", monospace;
    font-size: 0.875em;
}
pre {
    background: #f4f4f5; border: 1px solid #e1e4e8;
    border-radius: 6px; padding: 14px 16px;
    overflow-x: auto; margin: 1em 0;
}
pre code { background: none; padding: 0; font-size: 0.875em; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 0.95em; }
th, td { border: 1px solid #d0d7de; padding: 8px 12px; text-align: left; }
th { background: #f4f4f5; font-weight: 600; }
tr:nth-child(even) { background: #fafafa; }
blockquote { border-left: 3px solid #0969da; padding: 4px 0 4px 16px; color: #555; margin: 1em 0; }
hr { border: none; border-top: 1px solid #e1e4e8; margin: 2em 0; }
img { max-width: 100%; }
"""


def _pdf_via_weasyprint(md_path, output_path, rendered_html):
    from weasyprint import HTML, CSS
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body>{rendered_html}</body></html>"""
    allowed_dir = str(Path(md_path).parent)
    HTML(string=html, base_url=allowed_dir).write_pdf(
        str(output_path),
        stylesheets=[CSS(string=PRINT_CSS)],
        url_fetcher=_make_restricted_fetcher(allowed_dir),
    )


def _pdf_via_pandoc(md_path, output_path):
    engines = ["xelatex", "lualatex", "pdflatex", None]
    for engine in engines:
        cmd = ["pandoc", str(md_path), "-o", str(output_path),
               "--variable=geometry:margin=2cm", "--variable=fontsize=11pt"]
        if engine:
            cmd += [f"--pdf-engine={engine}"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            return
    raise RuntimeError(result.stderr or "pandoc failed")


def create_app(target_file, access_token, platform="windows", edit_mode=False):
    try:
        from flask import Flask, render_template, send_file, abort, jsonify, request
        import markdown2
    except ImportError as e:
        print(f"peek: Missing dependency — {e}")
        print("      Run: pip3 install flask markdown2")
        sys.exit(1)

    _win_downloads = _windows_downloads_path() if platform == "windows" else None
    _save_default = _default_save_display(platform, _win_downloads, Path(target_file).name)

    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
    app = Flask(__name__, template_folder=template_dir)
    app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_BYTES

    # ── Token validation ──────────────────────────────────────────────────────

    def _valid_token(req):
        return (
            req.cookies.get("peek_token") == access_token
            or req.args.get("token") == access_token
        )

    @app.before_request
    def enforce_token():
        if not _valid_token(request):
            abort(403)

    @app.after_request
    def apply_security_headers(response):
        if request.args.get("token") == access_token:
            response.set_cookie(
                "peek_token", access_token,
                httponly=True, samesite="Strict", max_age=86400,
            )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Cache-Control"] = "no-store"
        return response

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _check_size(path):
        if path.stat().st_size > MAX_FILE_BYTES:
            abort(413)

    def _render_md(path):
        content = path.read_text(encoding="utf-8")
        raw_html = markdown2.markdown(
            content,
            extras=["fenced-code-blocks", "tables", "strike", "task_list", "header-ids"],
        )
        return _sanitize_html(raw_html)

    # ── Routes ────────────────────────────────────────────────────────────────

    @app.route("/")
    def view():
        path = Path(target_file)
        ext = path.suffix.lower()
        _check_size(path)

        common = dict(filename=path.name, platform=platform, edit_mode=edit_mode,
                      default_save_path=_save_default)

        if ext == ".pdf":
            return render_template("view.html", file_type="pdf", content="", **common)
        elif ext in (".md", ".markdown"):
            return render_template("view.html", file_type="markdown",
                                   content=_render_md(path), **common)
        elif ext == ".txt":
            content = path.read_text(encoding="utf-8")
            return render_template("view.html", file_type="text", content=content, **common)
        else:
            abort(415)

    @app.route("/content")
    def get_content():
        path = Path(target_file)
        _check_size(path)
        if path.suffix.lower() == ".pdf":
            abort(415)
        return jsonify({"content": path.read_text(encoding="utf-8")})

    @app.route("/save", methods=["POST"])
    def save_content():
        if not edit_mode:
            abort(403)
        # Refuse to write through symlinks
        if Path(target_file).is_symlink():
            abort(403)
        data = request.get_json(silent=True)
        if not data or "content" not in data:
            abort(400)
        Path(target_file).write_text(data["content"], encoding="utf-8")
        return jsonify({"success": True})

    @app.route("/raw")
    def serve_raw():
        path = Path(target_file)
        if path.suffix.lower() not in SUPPORTED_EXT:
            abort(415)
        _check_size(path)
        return send_file(target_file)

    @app.route("/source")
    def serve_source():
        """Return raw file bytes for browser-side File System Access API."""
        path = Path(target_file)
        if path.suffix.lower() not in SUPPORTED_EXT:
            abort(415)
        _check_size(path)
        return send_file(target_file, as_attachment=False)

    @app.route("/download")
    def download():
        """Save source file to platform Downloads folder and return path."""
        path = Path(target_file)
        _check_size(path)
        if platform == "windows":
            if _win_downloads:
                dest = _local_save(str(path), downloads_dir=_win_downloads)
                return jsonify({"success": True, "path": dest})
            return send_file(str(path), as_attachment=True, download_name=path.name)
        dest = _local_save(str(path))
        return jsonify({"success": True, "path": dest})

    @app.route("/generate-pdf", methods=["POST"])
    def generate_pdf():
        path = Path(target_file)
        _check_size(path)
        output_pdf = path.with_suffix(".pdf")
        rendered = _render_md(path)

        try:
            if subprocess.run(["which", "pandoc"], capture_output=True).returncode == 0:
                _pdf_via_pandoc(str(path), str(output_pdf))
            else:
                _pdf_via_weasyprint(str(path), str(output_pdf), rendered)
        except subprocess.TimeoutExpired:
            return jsonify({"success": False, "error": "PDF generation timed out (120s)"}), 500
        except Exception:
            try:
                _pdf_via_weasyprint(str(path), str(output_pdf), rendered)
            except Exception as e2:
                return jsonify({"success": False, "error": _sanitize_error(str(e2))}), 500

        if platform == "windows":
            # Windows: ブラウザ側の showSaveFilePicker で保存場所を選ばせる
            return jsonify({"success": True, "filename": output_pdf.name, "platform": "windows"})
        dest = _local_save(str(output_pdf))
        return jsonify({"success": True, "filename": output_pdf.name,
                        "path": dest, "platform": platform})

    # Extensions allowed as save-as destinations (edit targets only, not .pdf)
    _SAVEABLE_EXT = {'.md', '.markdown', '.txt'}

    @app.route("/save-as", methods=["POST"])
    def save_as():
        """Save file to a user-specified path (Save As dialog)."""
        data = request.get_json(silent=True) or {}
        dest_str = data.get("path", "").strip()
        content = data.get("content")  # present in edit mode, absent in view mode
        if not dest_str:
            return jsonify({"success": False, "error": "パスが空です"}), 400

        dest = Path(_normalize_path(dest_str)).expanduser().resolve()

        # Allow only supported text extensions to prevent writing to arbitrary files
        if dest.suffix.lower() not in (_SAVEABLE_EXT | {'.pdf'}):
            return jsonify({"success": False,
                            "error": f"保存できる拡張子: {', '.join(sorted(_SAVEABLE_EXT | {'.pdf'}))}"}), 400

        # Refuse to overwrite an existing symlink (prevents symlink-based file replacement)
        if dest.is_symlink():
            return jsonify({"success": False, "error": "シンボリックリンクへの保存は許可されていません"}), 400

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            if content is not None:
                dest.write_text(content, encoding="utf-8")
            else:
                shutil.copy2(target_file, str(dest))
            return jsonify({"success": True, "path": str(dest)})
        except Exception as e:
            return jsonify({"success": False, "error": "ファイルの保存に失敗しました"}), 500

    @app.route("/download-pdf")
    def download_pdf():
        """Send generated PDF to browser (fallback when Windows Downloads path unavailable)."""
        path = Path(target_file)
        output_pdf = path.with_suffix(".pdf")
        if not output_pdf.exists():
            abort(404)
        return send_file(str(output_pdf), as_attachment=True, download_name=output_pdf.name)

    return app


def _run_tui(target_file, edit_mode=False):
    try:
        from textual.app import App, ComposeResult
        from textual.widgets import Header, Footer, Markdown, Static, TextArea
        from textual.binding import Binding
        from textual.containers import Horizontal, Vertical, VerticalScroll
    except ImportError:
        print("peek: textual が見つかりません。セットアップを再実行してください:")
        print("      bash setup.sh")
        sys.exit(1)

    path = Path(target_file)
    ext = path.suffix.lower()

    if path.stat().st_size > MAX_FILE_BYTES:
        print(f"peek: ファイルが大きすぎます（上限 {MAX_FILE_BYTES // 1024 // 1024} MB）")
        sys.exit(1)

    file_type = 'text'
    content = ''

    if ext in ('.md', '.markdown'):
        content = path.read_text(encoding='utf-8')
        file_type = 'markdown'
    elif ext == '.txt':
        content = path.read_text(encoding='utf-8')
        file_type = 'text'
    elif ext == '.pdf':
        file_type = 'pdf'
        try:
            r = subprocess.run(
                ['pdftotext', target_file, '-'],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0 and r.stdout.strip():
                content = r.stdout
                file_type = 'text'
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # Load user settings
    settings = _load_settings()
    colors   = _get_theme_colors(settings)
    quit_key = settings.get("quit_key", "ctrl+q")
    save_key = settings.get("save_key", "ctrl+s")
    bg       = colors["bg"]
    surface  = colors["surface"]
    overlay  = colors.get("overlay", "#313244")
    text_c   = colors["text"]
    muted    = colors["muted"]
    vim_mode = (quit_key == "vim" or save_key == "vim")

    TYPE_LABEL = {'markdown': 'MD', 'text': 'TXT', 'pdf': 'PDF'}

    cmd_css = (
        f"#cmd-bar {{ dock: bottom; height: 1; background: {surface}; "
        f"color: {text_c}; padding: 0 1; display: none; }}\n"
        f"#cmd-bar.active {{ display: block; }}\n"
    ) if vim_mode else ""

    # ── TUI 編集モード (-t -e) ────────────────────────────────────────────────
    if edit_mode:
        if file_type == 'pdf':
            print("peek: PDF ファイルは TUI 編集モードに対応していません。")
            sys.exit(1)

        from rich.markdown import Markdown as RichMarkdown

        edit_bindings = []
        if quit_key != "vim":
            edit_bindings.append(Binding(quit_key, "quit", "終了", priority=True))
        if save_key != "vim":
            edit_bindings.append(Binding(save_key, "save", "保存", priority=True))

        class PeekEditApp(App):
            TITLE = path.name
            SUB_TITLE = f"{TYPE_LABEL.get(file_type, '')}  ✎"
            CSS = (
                f"Screen         {{ background: {bg}; }}\n"
                f"Header         {{ background: {surface}; color: {text_c}; }}\n"
                f"Footer         {{ background: {surface}; color: {muted}; }}\n"
                f"Horizontal     {{ height: 1fr; }}\n"
                f"#editor-pane   {{ width: 1fr; height: 1fr; border-right: solid {overlay}; }}\n"
                f"#preview-pane  {{ width: 1fr; height: 1fr; background: {bg}; }}\n"
                f"TextArea       {{ height: 1fr; background: {bg}; }}\n"
                f"#preview-content {{ padding: 0 1; color: {text_c}; }}\n"
                + cmd_css
            )
            BINDINGS = edit_bindings
            _cmd_mode = False
            _cmd_buf = ""

            def compose(self) -> ComposeResult:
                yield Header(show_clock=False)
                if file_type == 'markdown':
                    with Horizontal():
                        with Vertical(id='editor-pane'):
                            yield TextArea(content, id='editor', language='markdown')
                        with VerticalScroll(id='preview-pane'):
                            yield Static(RichMarkdown(content), id='preview-content')
                else:
                    yield TextArea(content, id='editor')
                if vim_mode:
                    yield Static("", id="cmd-bar")
                yield Footer()

            def on_text_area_changed(self, event: TextArea.Changed) -> None:
                if file_type == 'markdown':
                    new_text = self.query_one('#editor', TextArea).text
                    self.query_one('#preview-content', Static).update(RichMarkdown(new_text))

            def action_save(self) -> None:
                editor = self.query_one('#editor', TextArea)
                path.write_text(editor.text, encoding='utf-8')
                self.notify("保存しました")

            def on_key(self, event) -> None:
                if not vim_mode:
                    return
                # Let TextArea consume its own keys
                if isinstance(self.focused, TextArea):
                    return
                if not self._cmd_mode:
                    if event.character == ":":
                        self._cmd_mode = True
                        self._cmd_buf = ":"
                        self._update_cmd_bar()
                        event.prevent_default()
                else:
                    event.prevent_default()
                    if event.key == "escape":
                        self._exit_cmd_mode()
                    elif event.key == "enter":
                        self._run_cmd(self._cmd_buf[1:])
                    elif event.key == "backspace":
                        if len(self._cmd_buf) > 1:
                            self._cmd_buf = self._cmd_buf[:-1]
                            self._update_cmd_bar()
                        else:
                            self._exit_cmd_mode()
                    elif event.character:
                        self._cmd_buf += event.character
                        self._update_cmd_bar()

            def _update_cmd_bar(self) -> None:
                bar = self.query_one("#cmd-bar", Static)
                bar.update(self._cmd_buf)
                bar.add_class("active")

            def _exit_cmd_mode(self) -> None:
                self._cmd_mode = False
                self._cmd_buf = ""
                bar = self.query_one("#cmd-bar", Static)
                bar.update("")
                bar.remove_class("active")

            def _run_cmd(self, cmd: str) -> None:
                self._exit_cmd_mode()
                if cmd == "w":
                    self.action_save()
                elif cmd in ("wq", "x"):
                    self.action_save()
                    self.exit()
                elif cmd in ("q", "q!"):
                    self.exit()

        PeekEditApp().run()
        return

    # ── TUI 閲覧モード (-t) ───────────────────────────────────────────────────
    view_bindings = []
    if quit_key != "vim":
        view_bindings.append(Binding(quit_key, "quit", "終了"))

    class PeekApp(App):
        TITLE = path.name
        SUB_TITLE = TYPE_LABEL.get(file_type, '')
        CSS = (
            f"Screen        {{ background: {bg}; }}\n"
            f"Header        {{ background: {surface}; color: {text_c}; }}\n"
            f"Footer        {{ background: {surface}; color: {muted}; }}\n"
            f"Markdown      {{ height: 1fr; padding: 1 2; background: {bg}; }}\n"
            f"VerticalScroll{{ height: 1fr; background: {bg}; }}\n"
            f"#txt          {{ color: {text_c}; padding: 1 2; }}\n"
            f"#pdf-info     {{ color: #f9e2af; padding: 2 4; }}\n"
            + cmd_css
        )
        BINDINGS = view_bindings
        _cmd_mode = False
        _cmd_buf = ""

        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            if file_type == 'markdown':
                yield Markdown(content)
            elif file_type == 'text':
                lines = content.split('\n')
                w = len(str(len(lines)))
                numbered = '\n'.join(
                    f'{str(i + 1).rjust(w)}  {line}'
                    for i, line in enumerate(lines)
                )
                with VerticalScroll():
                    yield Static(numbered, id='txt')
            else:
                yield Static(
                    f"PDF: {path.name}\n\n"
                    "TUI では PDF を直接表示できません。\n\n"
                    "ブラウザで開くには:\n"
                    f"  peek -w {path.name}   (Windows)\n"
                    f"  peek -l {path.name}   (Linux)\n"
                    f"  peek -m {path.name}   (macOS)\n\n"
                    "poppler-utils をインストールするとテキスト抽出して表示できます:\n"
                    "  sudo apt install poppler-utils",
                    id='pdf-info',
                )
            if vim_mode:
                yield Static("", id="cmd-bar")
            yield Footer()

        def on_key(self, event) -> None:
            if not vim_mode:
                return
            if not self._cmd_mode:
                if event.character == ":":
                    self._cmd_mode = True
                    self._cmd_buf = ":"
                    self._update_cmd_bar()
                    event.prevent_default()
            else:
                event.prevent_default()
                if event.key == "escape":
                    self._exit_cmd_mode()
                elif event.key == "enter":
                    self._run_cmd(self._cmd_buf[1:])
                elif event.key == "backspace":
                    if len(self._cmd_buf) > 1:
                        self._cmd_buf = self._cmd_buf[:-1]
                        self._update_cmd_bar()
                    else:
                        self._exit_cmd_mode()
                elif event.character:
                    self._cmd_buf += event.character
                    self._update_cmd_bar()

        def _update_cmd_bar(self) -> None:
            bar = self.query_one("#cmd-bar", Static)
            bar.update(self._cmd_buf)
            bar.add_class("active")

        def _exit_cmd_mode(self) -> None:
            self._cmd_mode = False
            self._cmd_buf = ""
            bar = self.query_one("#cmd-bar", Static)
            bar.update("")
            bar.remove_class("active")

        def _run_cmd(self, cmd: str) -> None:
            self._exit_cmd_mode()
            if cmd in ("q", "q!"):
                self.exit()

    PeekApp().run()


def _load_settings():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                data = json.load(f)
            result = dict(DEFAULT_SETTINGS)
            result.update({k: v for k, v in data.items() if k in DEFAULT_SETTINGS})
            if "custom_colors" in data:
                result["custom_colors"] = {**DEFAULT_SETTINGS["custom_colors"], **data["custom_colors"]}
            return result
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)


def _save_settings(data):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _get_theme_colors(settings):
    theme = settings.get("theme", "catppuccin-mocha")
    if theme == "custom":
        base = dict(THEMES["catppuccin-mocha"])
        base.update(settings.get("custom_colors", {}))
        return base
    return dict(THEMES.get(theme, THEMES["catppuccin-mocha"]))


def _run_settings():
    try:
        from textual.app import App, ComposeResult
        from textual.widgets import Header, Footer, Static, Label, Button, Input, Select
        from textual.binding import Binding
        from textual.containers import Horizontal, Vertical, VerticalScroll
    except ImportError:
        print("peek: textual が見つかりません。セットアップを再実行してください:")
        print("      bash setup.sh")
        sys.exit(1)

    settings = _load_settings()

    THEME_OPTIONS = [
        ("Catppuccin Mocha (デフォルト)", "catppuccin-mocha"),
        ("Catppuccin Latte",              "catppuccin-latte"),
        ("Nord",                          "nord"),
        ("Gruvbox Dark",                  "gruvbox-dark"),
        ("Tokyo Night",                   "tokyo-night"),
        ("カスタム",                      "custom"),
    ]
    QUIT_OPTIONS = [
        ("Ctrl+Q",         "ctrl+q"),
        ("q (ビューのみ)", "q"),
        ("Escape",         "escape"),
        ("Vim (:q / :q!)", "vim"),
    ]
    SAVE_OPTIONS = [
        ("Ctrl+S",          "ctrl+s"),
        ("F5",              "f5"),
        ("Vim (:w / :wq)",  "vim"),
    ]

    cur_theme  = settings.get("theme", "catppuccin-mocha")
    cur_colors = settings.get("custom_colors", DEFAULT_SETTINGS["custom_colors"])
    cur_quit   = settings.get("quit_key", "ctrl+q")
    cur_save   = settings.get("save_key", "ctrl+s")

    COLOR_FIELDS = [
        ("bg",      "背景:"),
        ("surface", "サーフェス:"),
        ("overlay", "オーバーレイ:"),
        ("text",    "テキスト:"),
        ("muted",   "ミュート:"),
        ("accent",  "アクセント:"),
    ]

    class PeekSettingsApp(App):
        TITLE = "peek 設定"
        CSS = """
Screen           { background: #1e1e2e; }
Header           { background: #181825; color: #cdd6f4; }
Footer           { background: #181825; color: #6c7086; }
VerticalScroll   { height: 1fr; padding: 1 3; }
.section         { color: #89b4fa; text-style: bold; padding: 1 0 0 0; }
.hint            { color: #6c7086; padding: 0 0 0 2; }
.row             { height: 3; align: left middle; }
.lbl             { width: 18; color: #a6adc8; }
Select           { width: 38; }
Input            { width: 24; background: #313244; color: #cdd6f4; border: tall #313244; }
Input:focus      { border: tall #89b4fa; }
#custom-block    { display: none; padding: 0 2; }
#custom-block.show { display: block; }
.btn-row         { height: 3; padding: 1 0 0 0; align: left middle; }
Button           { margin-right: 2; }
"""
        BINDINGS = [Binding("ctrl+q", "quit", "保存せず閉じる")]

        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            with VerticalScroll():
                yield Label("── テーマ ───────────────────────────────────────────", classes="section")
                with Horizontal(classes="row"):
                    yield Label("テーマ:", classes="lbl")
                    yield Select(THEME_OPTIONS, value=cur_theme, id="sel-theme")

                yield Label("── カスタムカラー ────────────────────────────────────", classes="section")
                yield Label("  (テーマに「カスタム」を選択した場合のみ有効)", classes="hint")
                init_cls = "show" if cur_theme == "custom" else ""
                with Vertical(id="custom-block", classes=init_cls):
                    for cid, clabel in COLOR_FIELDS:
                        default = DEFAULT_SETTINGS["custom_colors"].get(cid, "#000000")
                        with Horizontal(classes="row"):
                            yield Label(clabel, classes="lbl")
                            yield Input(
                                value=cur_colors.get(cid, default),
                                id=f"col-{cid}",
                                placeholder=default,
                            )

                yield Label("── キーバインド ──────────────────────────────────────", classes="section")
                with Horizontal(classes="row"):
                    yield Label("終了キー:", classes="lbl")
                    yield Select(QUIT_OPTIONS, value=cur_quit, id="sel-quit")
                with Horizontal(classes="row"):
                    yield Label("保存キー:", classes="lbl")
                    yield Select(SAVE_OPTIONS, value=cur_save, id="sel-save")

                with Horizontal(classes="btn-row"):
                    yield Button("保存して閉じる", id="btn-save",   variant="primary")
                    yield Button("リセット",       id="btn-reset")
                    yield Button("キャンセル",     id="btn-cancel", variant="error")
            yield Footer()

        def on_select_changed(self, event: Select.Changed) -> None:
            if event.select.id != "sel-theme":
                return
            val = str(event.value) if event.value is not Select.BLANK else ""
            block = self.query_one("#custom-block")
            if val == "custom":
                block.add_class("show")
            else:
                block.remove_class("show")
                if val in THEMES:
                    c = THEMES[val]
                    for cid, _ in COLOR_FIELDS:
                        try:
                            self.query_one(f"#col-{cid}", Input).value = c.get(cid, "")
                        except Exception:
                            pass

        def on_button_pressed(self, event: Button.Pressed) -> None:
            bid = event.button.id
            if bid == "btn-cancel":
                self.exit()
            elif bid == "btn-reset":
                self._reset()
            elif bid == "btn-save":
                self._save()

        def _reset(self) -> None:
            try:
                self.query_one("#sel-theme", Select).value = "catppuccin-mocha"
                self.query_one("#sel-quit",  Select).value = "ctrl+q"
                self.query_one("#sel-save",  Select).value = "ctrl+s"
                c = THEMES["catppuccin-mocha"]
                for cid, _ in COLOR_FIELDS:
                    self.query_one(f"#col-{cid}", Input).value = c.get(cid, "")
                self.query_one("#custom-block").remove_class("show")
            except Exception:
                pass
            self.notify("デフォルト設定に戻しました")

        def _save(self) -> None:
            try:
                theme    = str(self.query_one("#sel-theme", Select).value or "catppuccin-mocha")
                quit_key = str(self.query_one("#sel-quit",  Select).value or "ctrl+q")
                save_key = str(self.query_one("#sel-save",  Select).value or "ctrl+s")
            except Exception:
                self.notify("設定の読み取りに失敗しました", severity="error")
                return
            custom = {}
            for cid, _ in COLOR_FIELDS:
                dflt = DEFAULT_SETTINGS["custom_colors"].get(cid, "#000000")
                raw = ""
                try:
                    raw = self.query_one(f"#col-{cid}", Input).value.strip()
                except Exception:
                    pass
                custom[cid] = raw if (raw.startswith("#") and len(raw) in (4, 7)) else dflt
            _save_settings({"theme": theme, "custom_colors": custom,
                            "quit_key": quit_key, "save_key": save_key})
            self.notify("設定を保存しました")
            self.call_after_refresh(self.exit)

    PeekSettingsApp().run()


def _run_easter_egg():
    try:
        from textual.app import App, ComposeResult
        from textual.widgets import Static
        from textual.binding import Binding
        from textual.containers import Vertical
    except ImportError:
        print(f"\n👀  peek! {VERSION}\n")
        return

    wall_w = min(shutil.get_terminal_size((80, 24)).columns - 4, 68)
    ART_HEIGHT = 6
    WALL = "─" * wall_w

    EYES_NORMAL = "◉   ◉"
    EYES_BLINK  = "-   -"
    EYES_RIGHT  = "·   ◉"
    EYES_LEFT   = "◉   ·"

    def _art(eyes, n):
        lines = [
            "  /\\_____/\\  ",
            f" /  {eyes}  \\ ",
            "( =   ^   = )",
            " )  peek!  ( ",
        ]
        visible = lines[len(lines) - n:] if n > 0 else []
        return "\n".join([""] * (ART_HEIGHT - len(visible)) + visible)

    STAGES = [
        (0, EYES_NORMAL, 0.5),
        (1, EYES_NORMAL, 0.35),
        (2, EYES_NORMAL, 0.3),
        (3, EYES_NORMAL, 0.3),
        (4, EYES_NORMAL, 0.4),
        (4, EYES_BLINK,  0.18),
        (4, EYES_NORMAL, 0.4),
        (4, EYES_RIGHT,  0.5),
        (4, EYES_LEFT,   0.5),
        (4, EYES_NORMAL, 0.3),
        (4, EYES_BLINK,  0.18),
        (4, EYES_NORMAL, 0.5),
        (3, EYES_NORMAL, 0.3),
        (2, EYES_NORMAL, 0.3),
        (1, EYES_NORMAL, 0.3),
        (0, EYES_NORMAL, 0.4),
    ]

    class _EggApp(App):
        CSS = f"""
Screen {{ background: #1e1e2e; align: center middle; }}
#title {{ width: 30; height: 1; color: #f9e2af; text-style: bold; text-align: center; }}
#art   {{ width: 20; height: {ART_HEIGHT}; color: #cdd6f4; text-align: center; }}
#wall  {{ width: {wall_w}; color: #89b4fa; text-align: center; }}
#hint  {{ color: #6c7086; text-align: center; margin-top: 1; }}
"""
        BINDINGS = [
            Binding("q",      "quit", "", show=False),
            Binding("escape", "quit", "", show=False),
            Binding("space",  "quit", "", show=False),
            Binding("enter",  "quit", "", show=False),
        ]

        def compose(self) -> ComposeResult:
            with Vertical():
                yield Static("", id="title")
                yield Static(_art(EYES_NORMAL, 0), id="art")
                yield Static(WALL, id="wall")
                yield Static("any key to exit", id="hint")

        def on_mount(self) -> None:
            self._stage = 0
            self._title_on = False
            self._next()

        def _next(self) -> None:
            if self._stage < len(STAGES):
                self.set_timer(STAGES[self._stage][2], self._tick)
            else:
                self.set_timer(0.5, self.exit)

        def _tick(self) -> None:
            if self._stage >= len(STAGES):
                self.exit()
                return
            n, eyes, _ = STAGES[self._stage]
            self.query_one("#art", Static).update(_art(eyes, n))
            if n == 4:
                self._title_on = True
            if self._title_on and n > 0:
                self.query_one("#title", Static).update(f"✦  peek {VERSION}  ✦")
            elif n == 0:
                self._title_on = False
                self.query_one("#title", Static).update("")
            self._stage += 1
            self._next()

        def on_key(self, event) -> None:
            self.exit()

    _EggApp().run()


# ── easter egg: matrix ────────────────────────────────────────────────────────
def _run_matrix():
    try:
        from textual.app import App, ComposeResult
        from textual.widgets import Static
        from textual.binding import Binding
        import random
    except ImportError:
        print("\n01001110 01001111 peek\n")
        return

    KATAKANA = "ｦｧｨｩｪｫｬｭｮｯｰｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ"
    CHARS = KATAKANA + "0123456789"

    class _MatrixApp(App):
        CSS = """
Screen { background: #0d0d0d; }
#canvas { width: 100%; height: 100%; }
#hint { dock: bottom; color: #1a4a1a; text-align: center; height: 1; }
"""
        BINDINGS = [
            Binding("q",      "quit", "", show=False),
            Binding("escape", "quit", "", show=False),
            Binding("space",  "quit", "", show=False),
            Binding("enter",  "quit", "", show=False),
        ]

        def compose(self) -> ComposeResult:
            yield Static("", id="canvas")
            yield Static("any key to exit", id="hint")

        def on_mount(self) -> None:
            cols, rows = shutil.get_terminal_size((80, 24))
            self._cols = cols
            self._rows = rows - 1
            self._drops = [random.randint(-rows, 0) for _ in range(cols)]
            self._speeds = [random.choice([1, 1, 1, 2]) for _ in range(cols)]
            self._chars = [
                [random.choice(CHARS) for _ in range(rows)] for _ in range(cols)
            ]
            self.set_interval(0.08, self._tick)

        def _tick(self) -> None:
            cols, rows = self._cols, self._rows
            grid = [[" "] * cols for _ in range(rows)]
            for c in range(cols):
                head = self._drops[c]
                for r in range(rows):
                    dist = head - r
                    if dist == 0:
                        ch = self._chars[c][r % rows]
                        grid[r][c] = f"\x1b[1;92m{ch}\x1b[0m"
                    elif 0 < dist <= 6:
                        ch = self._chars[c][r % rows]
                        brightness = ["32", "32", "32", "2;32", "2;32", "2;32"][dist - 1]
                        grid[r][c] = f"\x1b[{brightness}m{ch}\x1b[0m"
                self._drops[c] += self._speeds[c]
                if self._drops[c] > rows + 6:
                    self._drops[c] = random.randint(-8, 0)
                    self._chars[c] = [random.choice(CHARS) for _ in range(rows)]
            lines = ["".join(grid[r]) for r in range(rows)]
            self.query_one("#canvas", Static).update("\n".join(lines))

        def on_key(self, event) -> None:
            self.exit()

    _MatrixApp().run()


# ── easter egg: aquarium ──────────────────────────────────────────────────────
def _run_aquarium():
    try:
        from textual.app import App, ComposeResult
        from textual.widgets import Static
        from textual.binding import Binding
        import random
    except ImportError:
        print("\n><((º>  🐠  <º)))><\n")
        return

    FISH_R = ["  ><((º> ", " ><((º>  ", "><((º>   "]
    FISH_L = [" <º)))><  ", "  <º)))>< ", "   <º)))><"]
    SMALL_R = [" >((º>", ">((º> "]
    SMALL_L = ["<º))< ", " <º))<"]
    BUBBLE = ["·", "o", "°"]
    SEAWEED = ["|", "¦", "ı", "¦"]

    class _AquariumApp(App):
        CSS = """
Screen { background: #001830; align: center middle; }
#tank  { width: 72; height: 20; }
#hint  { color: #1a3a4a; text-align: center; margin-top: 1; }
"""
        BINDINGS = [
            Binding("q",      "quit", "", show=False),
            Binding("escape", "quit", "", show=False),
            Binding("space",  "quit", "", show=False),
            Binding("enter",  "quit", "", show=False),
        ]

        def compose(self) -> ComposeResult:
            yield Static("", id="tank")
            yield Static("any key to exit", id="hint")

        def on_mount(self) -> None:
            W, H = 70, 18
            self._W = W
            self._H = H
            import random as rnd
            self._fish = [
                {"x": rnd.randint(0, W - 10), "y": rnd.randint(1, H - 4),
                 "dx": 1, "frames": FISH_R, "alt": FISH_L, "frame": 0},
                {"x": rnd.randint(0, W - 10), "y": rnd.randint(1, H - 4),
                 "dx": -1, "frames": FISH_L, "alt": FISH_R, "frame": 1},
                {"x": rnd.randint(0, W - 8),  "y": rnd.randint(1, H - 4),
                 "dx": 1, "frames": SMALL_R, "alt": SMALL_L, "frame": 0},
                {"x": rnd.randint(0, W - 8),  "y": rnd.randint(1, H - 4),
                 "dx": -1, "frames": SMALL_L, "alt": SMALL_R, "frame": 1},
            ]
            self._bubbles = [
                {"x": rnd.randint(2, W - 2), "y": rnd.randint(2, H - 2),
                 "char": rnd.choice(BUBBLE)} for _ in range(10)
            ]
            self._seaweed_x = [rnd.randint(2, W - 2) for _ in range(5)]
            self._tick_n = 0
            self.set_interval(0.18, self._tick)

        def _tick(self) -> None:
            import random as rnd
            W, H = self._W, self._H
            self._tick_n += 1

            grid = [[" "] * W for _ in range(H)]

            # border
            for c in range(W):
                grid[0][c]     = "\x1b[34m─\x1b[0m"
                grid[H-1][c]   = "\x1b[34m─\x1b[0m"
            for r in range(H):
                grid[r][0]     = "\x1b[34m│\x1b[0m"
                grid[r][W-1]   = "\x1b[34m│\x1b[0m"
            grid[0][0] = grid[0][W-1] = "\x1b[34m─\x1b[0m"

            # seaweed
            for sx in self._seaweed_x:
                sw_char = SEAWEED[self._tick_n % len(SEAWEED)]
                for r in range(H - 4, H - 1):
                    if 1 <= sx < W - 1:
                        grid[r][sx] = f"\x1b[32m{sw_char}\x1b[0m"

            # bubbles drift up
            for b in self._bubbles:
                r, c = int(b["y"]), int(b["x"])
                if 1 <= r < H - 1 and 1 <= c < W - 1:
                    grid[r][c] = f"\x1b[36m{b['char']}\x1b[0m"
                b["y"] -= 0.3
                if b["y"] < 1:
                    b["y"] = H - 2
                    b["x"] = rnd.randint(2, W - 2)
                    b["char"] = rnd.choice(BUBBLE)

            # fish
            for f in self._fish:
                body = f["frames"][f["frame"] % len(f["frames"])]
                f["frame"] += 1
                x, y = int(f["x"]), int(f["y"])
                color = "\x1b[33m" if len(body) > 7 else "\x1b[35m"
                for i, ch in enumerate(body):
                    cx = x + i
                    if 1 <= y < H - 1 and 1 <= cx < W - 1:
                        grid[y][cx] = f"{color}{ch}\x1b[0m"
                f["x"] += f["dx"] * 0.6
                if f["x"] >= W - len(body) - 1:
                    f["dx"] = -1
                    f["frames"], f["alt"] = f["alt"], f["frames"]
                if f["x"] <= 1:
                    f["dx"] = 1
                    f["frames"], f["alt"] = f["alt"], f["frames"]

            # sand
            sand = "·" * (W - 2)
            grid[H-2][1:W-1] = list(f"\x1b[33m{sand}\x1b[0m")

            lines = ["".join(grid[r]) for r in range(H)]
            self.query_one("#tank", Static).update("\n".join(lines))

        def on_key(self, event) -> None:
            self.exit()

    _AquariumApp().run()


# ── easter egg: zen ───────────────────────────────────────────────────────────
def _run_zen():
    try:
        from textual.app import App, ComposeResult
        from textual.widgets import Static
        from textual.binding import Binding
        from textual.containers import Vertical
        import random
    except ImportError:
        print(f"\n☽\n\n「開けば世界が見える」\n\n  -- peek {VERSION}\n")
        return

    QUOTES = [
        "「開けば、世界が見える」",
        "「静寂の中に、答えがある」",
        "「見ることは、知ること」",
        "「一行の文字が、旅の始まり」",
        "「ファイルは鏡、読む者を映す」",
        "「急がば、peek せよ」",
        "「余白を恐れるな」",
    ]

    import random
    quote = random.choice(QUOTES)

    MOON = "    ☽    "
    MOUNTAIN = [
        "        /\\        /\\       ",
        "       /  \\      /  \\      ",
        "      /    \\    /    \\     ",
        "     /      \\  /      \\    ",
        "    /        \\/        \\   ",
        "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
    ]

    STAGES = (
        # (moon_alpha, mountain_lines, quote_alpha, dt)
        (0, 0, 0, 0.3),
        (1, 0, 0, 0.5),
        (1, 1, 0, 0.3),
        (1, 2, 0, 0.3),
        (1, 3, 0, 0.3),
        (1, 4, 0, 0.3),
        (1, 5, 0, 0.3),
        (1, 6, 0, 0.5),
        (1, 6, 1, 0.5),
        (1, 6, 2, 0.6),
    )

    MOON_COLORS = ["", "\x1b[2;33m", "\x1b[33m"]
    QUOTE_COLORS = ["", "\x1b[2;37m", "\x1b[37m"]

    class _ZenApp(App):
        CSS = f"""
Screen {{ background: #0a0a14; align: center middle; }}
#moon    {{ height: 1; color: #f9e2af; text-align: center; text-style: bold; }}
#mountain{{ height: 7; color: #7aa2f7; text-align: center; }}
#quote   {{ height: 1; color: #cdd6f4; text-align: center; margin-top: 1; }}
#author  {{ height: 1; color: #6c7086; text-align: center; }}
#hint    {{ height: 1; color: #313244; text-align: center; margin-top: 2; }}
"""
        BINDINGS = [
            Binding("q",      "quit", "", show=False),
            Binding("escape", "quit", "", show=False),
            Binding("space",  "quit", "", show=False),
            Binding("enter",  "quit", "", show=False),
        ]

        def compose(self) -> ComposeResult:
            with Vertical():
                yield Static("", id="moon")
                yield Static("", id="mountain")
                yield Static("", id="quote")
                yield Static("", id="author")
                yield Static("any key to exit", id="hint")

        def on_mount(self) -> None:
            self._stage = 0
            self._next()

        def _next(self) -> None:
            if self._stage < len(STAGES):
                self.set_timer(STAGES[self._stage][3], self._tick)

        def _tick(self) -> None:
            if self._stage >= len(STAGES):
                return
            moon_a, mt_n, qt_a, _ = STAGES[self._stage]
            mc = MOON_COLORS[moon_a]
            self.query_one("#moon", Static).update(f"{mc}{MOON}\x1b[0m" if moon_a else "")
            mt_text = "\n".join(MOUNTAIN[:mt_n]) if mt_n else ""
            self.query_one("#mountain", Static).update(mt_text)
            qc = QUOTE_COLORS[qt_a]
            self.query_one("#quote", Static).update(f"{qc}{quote}\x1b[0m" if qt_a else "")
            if qt_a == 2:
                self.query_one("#author", Static).update(f"\x1b[2;37m-- peek {VERSION}\x1b[0m")
            self._stage += 1
            self._next()

        def on_key(self, event) -> None:
            self.exit()

    _ZenApp().run()


# ── easter egg: 404 ───────────────────────────────────────────────────────────
def _run_404():
    try:
        from textual.app import App, ComposeResult
        from textual.widgets import Static
        from textual.binding import Binding
        from textual.containers import Vertical
        import random
    except ImportError:
        print("\n(╯°□°）╯︵ ┻━┻\n\nファイルが見つかりません。でも peek はあきらめない。\n")
        return

    import random

    MSGS = [
        "探したけど…なかった。",
        "ファイル、蒸発しました。",
        "404: 存在しない未来。",
        "どこかに行ってしまった。",
        "宇宙のどこかにあるはず。",
        "消えた。でも peek はここにいる。",
    ]

    FLIP_STAGES = [
        ("( °□°）      ┳━┳",   0.3),
        ("( °□°）つ    ┳━┳",   0.25),
        ("(╯°□°）╯     ┳━┳",   0.2),
        ("(╯°□°）╯︵   ┳━┳",   0.15),
        ("(╯°□°）╯︵   ┻━┻",   0.3),
        ("(╯°□°）╯︵ ┻━┻",     0.5),
    ]

    msg = random.choice(MSGS)

    class _404App(App):
        CSS = """
Screen  { background: #1e1e2e; align: center middle; }
#flip   { height: 1; color: #f38ba8; text-style: bold; text-align: center; }
#msg    { height: 1; color: #cdd6f4; text-align: center; margin-top: 1; }
#sub    { height: 1; color: #6c7086; text-align: center; }
#hint   { height: 1; color: #313244; text-align: center; margin-top: 2; }
"""
        BINDINGS = [
            Binding("q",      "quit", "", show=False),
            Binding("escape", "quit", "", show=False),
            Binding("space",  "quit", "", show=False),
            Binding("enter",  "quit", "", show=False),
        ]

        def compose(self) -> ComposeResult:
            with Vertical():
                yield Static("", id="flip")
                yield Static("", id="msg")
                yield Static("", id="sub")
                yield Static("any key to exit", id="hint")

        def on_mount(self) -> None:
            self._stage = 0
            self._next()

        def _next(self) -> None:
            if self._stage < len(FLIP_STAGES):
                self.set_timer(FLIP_STAGES[self._stage][1], self._tick)
            else:
                self.query_one("#msg",  Static).update(msg)
                self.query_one("#sub",  Static).update(f"peek {VERSION} はあきらめない。")

        def _tick(self) -> None:
            if self._stage >= len(FLIP_STAGES):
                return
            text, _ = FLIP_STAGES[self._stage]
            self.query_one("#flip", Static).update(text)
            self._stage += 1
            self._next()

        def on_key(self, event) -> None:
            self.exit()

    _404App().run()


def _do_update():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    venv_pip = str(Path.home() / ".local" / "share" / "peek-venv" / "bin" / "pip")
    req_file = os.path.join(script_dir, "requirements.txt")

    print("peek: Pulling latest changes...")
    result = subprocess.run(["git", "-C", script_dir, "pull"])
    if result.returncode != 0:
        print("peek: git pull failed. Check your network or remote settings.")
        sys.exit(1)

    if os.path.isfile(venv_pip) and os.path.isfile(req_file):
        print("peek: Updating dependencies...")
        subprocess.run([venv_pip, "install", "-r", req_file, "--quiet"])

    print("peek: Done! Run 'peek --version' to verify.")


_ALL_FLAGS = [
    '-t', '--tui', '-b', '--browser',
    '-w', '--windows', '-l', '--linux', '-m', '--mac',
    '-e', '--edit', '-s', '--settings',
    '--update', '--help-en', '--help-ja', '--version', '-v',
    '--peek', '--matrix', '--aquarium', '--zen', '--404',
]
_SHORT_FLAGS = set('tblmwevs')


def _suggest_flag(arg):
    # e.g. "-te" → "-t -e"
    if (arg.startswith('-') and not arg.startswith('--')
            and len(arg) > 2
            and all(c in _SHORT_FLAGS for c in arg[1:])):
        return ' '.join(f'-{c}' for c in arg[1:])
    matches = difflib.get_close_matches(arg, _ALL_FLAGS, n=1, cutoff=0.6)
    return matches[0] if matches else None


def main():
    args = sys.argv[1:]

    if not args:
        print(f"peek {VERSION}  —  ファイルビューア for WSL / Linux / macOS")
        print()
        print("  使い方: peek [オプション] <ファイル>")
        print()
        print("    peek README.md          ブラウザで開く（デフォルト）")
        print("    peek -t README.md       TUI で開く")
        print("    peek -t -e README.md    TUI エディタ（リアルタイムプレビュー）")
        print("    peek -e README.md       ブラウザライブエディタ")
        print("    peek -s                 設定（テーマ・カラー・キーバインド）")
        print()
        print("  詳細: peek --help-ja  /  peek --help-en")
        sys.exit(1)

    if args[0] in ("-h", "--help", "--help-en"):
        print(HELP_EN)
        sys.exit(0)

    if args[0] == "--help-ja":
        print(HELP_JA)
        sys.exit(0)

    if args[0] in ("-v", "--version"):
        print(f"peek {VERSION}")
        sys.exit(0)

    if args[0] in ("--update", "update"):
        _do_update()
        sys.exit(0)

    if args[0] == "--peek":
        _run_easter_egg()
        sys.exit(0)

    if args[0] == "--matrix":
        _run_matrix()
        sys.exit(0)

    if args[0] == "--aquarium":
        _run_aquarium()
        sys.exit(0)

    if args[0] == "--zen":
        _run_zen()
        sys.exit(0)

    if args[0] == "--404":
        _run_404()
        sys.exit(0)

    if args[0] in ("-s", "--settings"):
        if len(args) > 1:
            print("peek: '-s' は単独で使用してください（他のオプションやファイルと組み合わせられません）")
            print("      詳細: peek --help-ja  /  peek --help-en")
            sys.exit(1)
        _run_settings()
        sys.exit(0)

    # Parse flags
    platform = _detect_default_platform()
    tui_mode = False
    edit_mode = False
    clean_args = []
    for arg in args:
        if arg in ("-t", "--tui"):
            tui_mode = True
        elif arg in ("-b", "--browser"):
            tui_mode = False
        elif arg in ("-w", "--windows"):
            platform = "windows"
            tui_mode = False
        elif arg in ("-l", "--linux"):
            platform = "linux"
            tui_mode = False
        elif arg in ("-m", "--mac"):
            platform = "mac"
            tui_mode = False
        elif arg in ("-e", "--edit"):
            edit_mode = True
        elif arg in ("-s", "--settings"):
            print("peek: '-s' は単独で使用してください（他のオプションやファイルと組み合わせられません）")
            print("      詳細: peek --help-ja  /  peek --help-en")
            sys.exit(1)
        elif arg.startswith("-"):
            suggestion = _suggest_flag(arg)
            print(f"peek: 不明なオプション '{arg}'")
            if suggestion:
                print(f"      もしかして: {suggestion}")
            print("      詳細: peek --help-ja  /  peek --help-en")
            sys.exit(1)
        else:
            clean_args.append(arg)
    args = clean_args

    if not args:
        print("peek: ファイルが指定されていません。")
        print("      使い方: peek [オプション] <ファイル>")
        sys.exit(1)

    file_path = args[0]

    if not os.path.exists(file_path):
        if edit_mode:
            new_path = Path(file_path)
            new_path.parent.mkdir(parents=True, exist_ok=True)
            new_path.touch()
            print(f"peek: '{new_path.name}' を作成しました")
        else:
            print(f"peek: '{file_path}': No such file")
            sys.exit(1)

    target_file = os.path.abspath(file_path)
    ext = Path(target_file).suffix.lower()

    if ext not in SUPPORTED_EXT:
        print(f"peek: Unsupported file type '{ext}'")
        print(f"      Supported: {', '.join(sorted(SUPPORTED_EXT))}")
        sys.exit(1)

    if tui_mode:
        _run_tui(target_file, edit_mode=edit_mode)
        sys.exit(0)

    port = find_free_port()
    access_token = secrets.token_urlsafe(32)
    app = create_app(target_file, access_token, platform, edit_mode)

    mode_label = {"linux": "Linux ~/Downloads/", "mac": "macOS ~/Downloads/"}.get(platform, "Windows")
    edit_label = " [edit]" if edit_mode else ""
    print(f"peek: {Path(target_file).name}  [{mode_label}]{edit_label}")
    print(f"      http://localhost:{port}/?token=***")

    if edit_mode:
        # Fork: parent exits (freeing terminal), child runs server
        try:
            pid = os.fork()
        except AttributeError:
            pid = 0  # os.fork unavailable, run in foreground

        if pid > 0:
            print(f"      PID {pid} — kill {pid} to stop")
            sys.exit(0)

        # Child: detach from terminal, run server silently
        os.setsid()
        sys.stdin = open(os.devnull)
        sys.stdout = open(os.devnull, "w")
        sys.stderr = open(os.devnull, "w")
    else:
        print("      Ctrl+C to close")

    threading.Thread(target=open_browser, args=(port, access_token, platform), daemon=True).start()

    import logging
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
