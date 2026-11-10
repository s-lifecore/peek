#!/usr/bin/env python3
"""peek - GUI file viewer for WSL / Linux / macOS terminals"""

import sys
import os
import shutil
import secrets
import subprocess
import threading
import time
import socket
from pathlib import Path

SUPPORTED_EXT = {'.md', '.markdown', '.txt', '.pdf'}
VERSION = "1.6.3"
MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB

HELP_EN = """peek {version} - GUI file viewer for WSL / Linux / macOS terminals

USAGE:
  peek [options] <file>

OPTIONS:
  -t, --tui             Open in TUI mode directly in the terminal
  -b, --browser         Open in browser with auto-detected platform (default)
  -w, --windows         Browser: Windows default browser, save to Windows
  -l, --linux           Browser: Linux default browser, save to ~/Downloads/
  -m, --mac             Browser: macOS default browser, save to ~/Downloads/
  -e, --edit            Edit mode: detach server + open live editor in browser
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
  -e, --edit            編集モード: バックグラウンドサーバー + ブラウザライブエディタ
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


def _local_save(src_path, filename=None):
    """Copy src_path to ~/Downloads/, return destination path string."""
    downloads = Path.home() / "Downloads"
    downloads.mkdir(exist_ok=True)
    dest = downloads / (filename or Path(src_path).name)
    shutil.copy2(str(src_path), str(dest))
    return str(dest)


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
        return markdown2.markdown(
            content,
            extras=["fenced-code-blocks", "tables", "strike", "task_list", "header-ids"],
        )

    # ── Routes ────────────────────────────────────────────────────────────────

    @app.route("/")
    def view():
        path = Path(target_file)
        ext = path.suffix.lower()
        _check_size(path)

        common = dict(filename=path.name, platform=platform, edit_mode=edit_mode)

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
        data = request.get_json(silent=True)
        if not data or "content" not in data:
            abort(400)
        Path(target_file).write_text(data["content"], encoding="utf-8")
        return jsonify({"success": True})

    @app.route("/raw")
    def serve_raw():
        _check_size(Path(target_file))
        return send_file(target_file)

    @app.route("/download")
    def download():
        """Download the source file (windows: browser DL / linux: ~/Downloads/)."""
        path = Path(target_file)
        _check_size(path)
        if platform in ("linux", "mac"):
            dest = _local_save(str(path))
            return jsonify({"success": True, "path": dest})
        return send_file(str(path), as_attachment=True, download_name=path.name)

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

        if platform in ("linux", "mac"):
            return jsonify({"success": True, "filename": output_pdf.name,
                            "path": str(output_pdf), "platform": platform})
        return jsonify({"success": True, "filename": output_pdf.name, "platform": "windows"})

    @app.route("/download-pdf")
    def download_pdf():
        """Send generated PDF to browser (windows mode only)."""
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

    TYPE_LABEL = {'markdown': 'MD', 'text': 'TXT', 'pdf': 'PDF'}

    # ── TUI 編集モード (-t -e) ────────────────────────────────────────────────
    if edit_mode:
        if file_type == 'pdf':
            print("peek: PDF ファイルは TUI 編集モードに対応していません。")
            sys.exit(1)

        class PeekEditApp(App):
            TITLE = path.name
            SUB_TITLE = f"{TYPE_LABEL.get(file_type, '')}  ✎"
            CSS = """
            Screen        { background: #1e1e2e; }
            Header        { background: #181825; color: #cdd6f4; }
            Footer        { background: #181825; color: #6c7086; }
            Horizontal    { height: 1fr; }
            #editor-pane  { width: 1fr; height: 1fr; border-right: solid #313244; }
            #preview-pane { width: 1fr; height: 1fr; }
            TextArea      { height: 1fr; background: #1e1e2e; }
            Markdown      { height: 1fr; padding: 0 1; background: #1e1e2e; }
            """
            BINDINGS = [
                Binding("ctrl+s", "save", "保存", priority=True),
                Binding("ctrl+q", "quit", "終了", priority=True),
            ]

            def compose(self) -> ComposeResult:
                yield Header(show_clock=False)
                if file_type == 'markdown':
                    with Horizontal():
                        with Vertical(id='editor-pane'):
                            yield TextArea(content, id='editor', language='markdown')
                        with Vertical(id='preview-pane'):
                            yield Markdown(content, id='preview')
                else:
                    yield TextArea(content, id='editor')
                yield Footer()

            async def on_text_area_changed(self, event: TextArea.Changed) -> None:
                if file_type == 'markdown':
                    new_text = self.query_one('#editor', TextArea).text
                    await self.query_one('#preview', Markdown).update(new_text)

            def action_save(self) -> None:
                editor = self.query_one('#editor', TextArea)
                path.write_text(editor.text, encoding='utf-8')
                self.notify("保存しました")

        PeekEditApp().run()
        return

    # ── TUI 閲覧モード (-t) ───────────────────────────────────────────────────
    class PeekApp(App):
        TITLE = path.name
        SUB_TITLE = TYPE_LABEL.get(file_type, '')
        CSS = """
        Screen        { background: #1e1e2e; }
        Header        { background: #181825; color: #cdd6f4; }
        Footer        { background: #181825; color: #6c7086; }
        Markdown      { height: 1fr; padding: 1 2; background: #1e1e2e; }
        VerticalScroll{ height: 1fr; background: #1e1e2e; }
        #txt          { color: #cdd6f4; padding: 1 2; }
        #pdf-info     { color: #f9e2af; padding: 2 4; }
        """
        BINDINGS = [Binding("q", "quit", "終了")]

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
            yield Footer()

    PeekApp().run()


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


def main():
    args = sys.argv[1:]

    if not args:
        print(f"peek {VERSION}  —  ファイルビューア for WSL / Linux / macOS")
        print()
        print("  使い方: peek [オプション] <ファイル>")
        print()
        print("    peek README.md       ブラウザで開く（デフォルト）")
        print("    peek -t README.md    TUI で開く")
        print("    peek -e README.md    ブラウザライブエディタ")
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
        elif arg.startswith("-"):
            print(f"peek: 不明なオプション '{arg}'")
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
