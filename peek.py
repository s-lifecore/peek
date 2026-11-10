#!/usr/bin/env python3
"""peek - GUI file viewer for WSL terminals"""

import sys
import os
import subprocess
import threading
import time
import socket
from pathlib import Path

SUPPORTED_EXT = {'.md', '.markdown', '.txt', '.pdf'}
VERSION = "1.0.0"

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


def open_browser(port):
    time.sleep(0.8)
    url = f"http://localhost:{port}"
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


def create_app(target_file):
    try:
        from flask import Flask, render_template, send_file, abort
        import markdown2
    except ImportError as e:
        print(f"peek: Missing dependency — {e}")
        print("      Run: pip3 install flask markdown2")
        sys.exit(1)

    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
    app = Flask(__name__, template_folder=template_dir)

    @app.route("/")
    def view():
        path = Path(target_file)
        ext = path.suffix.lower()

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
        return send_file(target_file)

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
    app = create_app(target_file)

    print(f"peek: {Path(target_file).name}")
    print(f"      http://localhost:{port}")
    print("      Ctrl+C to close")

    threading.Thread(target=open_browser, args=(port,), daemon=True).start()

    import logging
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
