#!/usr/bin/env python3
"""peek - GUI file viewer for WSL terminals"""

import sys
import os
import secrets
import subprocess
import threading
import time
import socket
from pathlib import Path

SUPPORTED_EXT = {'.md', '.markdown', '.txt', '.pdf'}
VERSION = "1.0.0"
MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB

HELP_EN = """peek {version} - GUI file viewer for WSL terminals

USAGE:
  peek <file>           Open a file in the browser
  peek --help-en        Show this help (English)
  peek --help-ja        Show help in Japanese
  peek --version        Show version

SUPPORTED FILE TYPES:
  .md / .markdown       Rendered Markdown with code highlighting
  .txt                  Plain text with monospace display
  .pdf                  Native PDF viewer in browser

EXAMPLES:
  peek README.md
  peek notes.txt
  peek document.pdf

HOW IT WORKS:
  Starts a local web server and opens your Windows browser.
  Press Ctrl+C in the terminal to stop the server.
""".format(version=VERSION)

HELP_JA = """peek {version} - WSL ターミナル用 GUI ファイルビューア

使い方:
  peek <ファイル>         ブラウザでファイルを開く
  peek --help-en         英語のヘルプを表示
  peek --help-ja         このヘルプを表示（日本語）
  peek --version         バージョンを表示

対応ファイル形式:
  .md / .markdown        コードハイライト付きマークダウンレンダリング
  .txt                   等幅フォントでプレーンテキスト表示
  .pdf                   ブラウザのネイティブ PDF ビューア

使用例:
  peek README.md
  peek notes.txt
  peek document.pdf

仕組み:
  ローカルウェブサーバーを起動し、Windows ブラウザで自動的に開きます。
  サーバーを停止するにはターミナルで Ctrl+C を押してください。
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


def open_browser(port, token):
    time.sleep(0.8)
    url = f"http://localhost:{port}/?token={token}"
    for cmd in [
        ["cmd.exe", "/c", "start", "", url],
        ["wslview", url],
        ["xdg-open", url],
    ]:
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except FileNotFoundError:
            continue
    print(f"peek: Could not open browser automatically. Visit {url}")


def _sanitize_error(msg):
    """Remove filesystem paths from error messages."""
    home = os.path.expanduser("~")
    return msg.replace(home, "~") if home != "~" else msg


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
    background: #f4f4f5;
    padding: 0.15em 0.4em;
    border-radius: 4px;
    font-family: "Consolas", "JetBrains Mono", monospace;
    font-size: 0.875em;
}
pre {
    background: #f4f4f5;
    border: 1px solid #e1e4e8;
    border-radius: 6px;
    padding: 14px 16px;
    overflow-x: auto;
    margin: 1em 0;
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


def create_app(target_file, access_token):
    try:
        from flask import Flask, render_template, send_file, abort, jsonify, request, make_response
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
        # Promote query-param token to cookie on first valid visit
        if request.args.get("token") == access_token:
            response.set_cookie(
                "peek_token", access_token,
                httponly=True, samesite="Strict", max_age=86400,
            )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Cache-Control"] = "no-store"
        return response

    # ── File size guard ───────────────────────────────────────────────────────

    def _check_size(path):
        if path.stat().st_size > MAX_FILE_BYTES:
            abort(413)

    # ── Routes ────────────────────────────────────────────────────────────────

    @app.route("/")
    def view():
        path = Path(target_file)
        ext = path.suffix.lower()
        _check_size(path)

        if ext == ".pdf":
            return render_template("view.html", file_type="pdf", filename=path.name, content="")

        elif ext in (".md", ".markdown"):
            content = path.read_text(encoding="utf-8")
            rendered = markdown2.markdown(
                content,
                extras=["fenced-code-blocks", "tables", "strike", "task_list", "header-ids"],
            )
            return render_template("view.html", file_type="markdown", filename=path.name, content=rendered)

        elif ext == ".txt":
            content = path.read_text(encoding="utf-8")
            return render_template("view.html", file_type="text", filename=path.name, content=content)

        else:
            abort(415)

    @app.route("/raw")
    def serve_raw():
        _check_size(Path(target_file))
        return send_file(target_file)

    @app.route("/generate-pdf", methods=["POST"])
    def generate_pdf():
        path = Path(target_file)
        _check_size(path)
        output_pdf = path.with_suffix(".pdf")

        content = path.read_text(encoding="utf-8")
        rendered = markdown2.markdown(
            content,
            extras=["fenced-code-blocks", "tables", "strike", "task_list", "header-ids"],
        )

        try:
            if subprocess.run(["which", "pandoc"], capture_output=True).returncode == 0:
                _pdf_via_pandoc(str(path), str(output_pdf))
            else:
                _pdf_via_weasyprint(str(path), str(output_pdf), rendered)
            return jsonify({"success": True, "filename": output_pdf.name})
        except subprocess.TimeoutExpired:
            return jsonify({"success": False, "error": "PDF generation timed out (120s)"}), 500
        except Exception:
            try:
                _pdf_via_weasyprint(str(path), str(output_pdf), rendered)
                return jsonify({"success": True, "filename": output_pdf.name})
            except Exception as e2:
                return jsonify({"success": False, "error": _sanitize_error(str(e2))}), 500

    @app.route("/download-pdf")
    def download_pdf():
        path = Path(target_file)
        output_pdf = path.with_suffix(".pdf")
        if not output_pdf.exists():
            abort(404)
        return send_file(str(output_pdf), as_attachment=True, download_name=output_pdf.name)

    return app


def main():
    args = sys.argv[1:]

    if not args:
        print("peek: No file specified. Try 'peek --help-en' or 'peek --help-ja'")
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

    port = find_free_port()
    access_token = secrets.token_urlsafe(32)
    app = create_app(target_file, access_token)

    print(f"peek: {Path(target_file).name}")
    print(f"      http://localhost:{port}/?token=***")
    print("      Ctrl+C to close")

    threading.Thread(target=open_browser, args=(port, access_token), daemon=True).start()

    import logging
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
