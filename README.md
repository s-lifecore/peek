# peek

WSL / Linux / macOS ターミナルから各種ファイルを開く CLI ビューアです。  
ブラウザでの高品質レンダリングと、ターミナルを離れない TUI モードの両方に対応しています。

```bash
peek README.md          # ブラウザで開く（デフォルト）
peek -t README.md       # TUI で開く
peek -s                 # 設定画面を開く
```

---

## 特徴

- **Markdown レンダリング** — 見出し・表・コードブロック・チェックリストをきれいに表示
- **TUI モード** — `-t` でターミナルを離れずに表示（textual ベース）
- **TUI エディタ** — `-t -e` でリアルタイムプレビュー付きの分割エディタ
- **ブラウザモード** — OS を自動検出し、適切なブラウザで開く
- **PDF ビューア** — ブラウザのネイティブ PDF ビューア、TUI では pdftotext でテキスト抽出
- **画像ビューア** — PNG / JPG / GIF / WEBP / SVG をブラウザで表示、TUI では chafa でプレビュー
- **CSV / TSV ビューア** — ブラウザでソート対応テーブル表示、TUI ではテキスト表形式
- **コードビューア** — `.py` `.js` `.html` `.css` など 40 以上の言語をシンタックスハイライト表示・編集対応
- **diff ビューア** — `peek file1 file2` で差分表示、`git diff | peek` でパイプ入力にも対応
- **テキスト表示** — 行番号付きで等幅フォント表示
- **PDF 生成** — `.md` から PDF を直接生成（pandoc / weasyprint 対応）
- **ライブ編集モード** — `-e` でサーバーをバックグラウンドに切り離し、ブラウザ上でリアルタイム編集
- **名前を付けて保存** — ブラウザのネイティブファイルダイアログで保存先を指定
- **設定画面** — `-s` でテーマ・カラー・フォント・キーバインドを TUI で変更
- **マルチプラットフォーム** — WSL / Linux / macOS に対応
- **ファイルダウンロード** — Windows は `C:\Users\...\Downloads\` へ、Linux / macOS は `~/Downloads/` に保存
- **セキュリティ** — アクセストークン認証、XSS・LFI 防止、セキュリティヘッダー付き
- **もしかして？** — 不明なオプション入力時に近いコマンドを提案
- **peak コマンド** — `peak` と打ち間違えたときにグラフアニメーションを表示（`sl` と同じ立場）

---

## インストール

### 1. リポジトリをクローン

```bash
git clone https://github.com/s-lifecore/peek.git ~/peek
cd ~/peek
```

### 2. セットアップスクリプトを実行

Python の仮想環境を作成し、依存パッケージをインストールします。

```bash
chmod +x setup.sh
./setup.sh
```

### 3. PATH を通す

**Bash の場合 (WSL / Linux):**
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

**Zsh の場合 (macOS / Linux):**
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### 4. 動作確認

```bash
peek --version
```

---

## 使い方

```bash
peek [オプション] <ファイル>
```

### ブラウザモード（デフォルト）

```bash
peek README.md          # OS を自動検出してブラウザで開く
peek -b README.md       # 同上（明示指定）
peek -w README.md       # Windows のデフォルトブラウザで開く
peek -l notes.txt       # Linux のデフォルトブラウザで開く
peek -m README.md       # macOS のデフォルトブラウザで開く
```

### TUI モード

```bash
peek -t README.md       # ターミナル内で Markdown をレンダリング
peek -t notes.txt       # 行番号付きテキスト表示
peek -t document.pdf    # pdftotext でテキスト抽出して表示
peek -t photo.png       # chafa でターミナル内プレビュー
peek -t data.csv        # テキスト表形式で表示
peek -t script.py       # シンタックスハイライト表示
peek -t -e index.html   # HTML ファイルをエディタで開く
```

**操作キー（デフォルト設定）:**

| キー | 動作 |
|------|------|
| `Ctrl+Q` | 終了 |
| `↑` `↓` | スクロール |
| `Page Up` `Page Down` | ページスクロール |
| `Home` `End` | 先頭 / 末尾 |

> キーバインドは `peek -s` で変更できます。Vim スタイル（`:q` / `:q!`）も選択可能です。

### TUI エディタモード

```bash
peek -t -e README.md    # 左: エディタ、右: Markdown プレビュー（リアルタイム）
```

**操作キー（デフォルト設定）:**

| キー | 動作 |
|------|------|
| `Ctrl+S` | 保存 |
| `Ctrl+Q` | 終了 |

### 編集モード（ブラウザ）

```bash
peek -e README.md
```

サーバーをバックグラウンドに切り離し、ターミナルを解放します。  
ブラウザ上でリアルタイム編集・保存ができます（Markdown はプレビュー付き）。  
終了するにはターミナルに表示された PID を使って `kill <PID>` します。

> **新規ファイル:** 存在しないファイル名を指定すると自動で作成します。

### 設定画面

```bash
peek -s
```

TUI の設定画面が起動します。保存すると `~/.config/peek/settings.json` に記録され、次回起動から反映されます。

| 設定項目 | 選択肢 |
|----------|--------|
| テーマ | Catppuccin Mocha（デフォルト）/ Latte / Nord / Gruvbox Dark / Tokyo Night / カスタム |
| カスタムカラー | bg / surface / overlay / text / muted / accent を hex 指定 |
| 本文フォント | システム標準 / Noto Sans JP / Inter / Georgia |
| コードフォント | システム標準 / JetBrains Mono / Fira Code / Source Code Pro |
| フォントサイズ | 小 (13px) / 中 (15px) / 大 (17px) |
| 終了キー | Ctrl+Q / q / Escape / Vim（`:q` / `:q!`） |
| 保存キー | Ctrl+S / F5 / Vim（`:w` / `:wq` / `:x`） |

> Noto Sans JP・Inter・JetBrains Mono・Fira Code・Source Code Pro は Google Fonts から自動読み込みされます。

---

## コマンドオプション

| オプション | 説明 |
|------------|------|
| `-t`, `--tui` | ターミナル内 TUI モードで表示 |
| `-b`, `--browser` | ブラウザで開く（デフォルト・OS 自動検出） |
| `-w`, `--windows` | ブラウザ: Windows のデフォルトブラウザ・Windows Downloads に保存 |
| `-l`, `--linux` | ブラウザ: Linux のデフォルトブラウザ・`~/Downloads/` に保存 |
| `-m`, `--mac` | ブラウザ: macOS のデフォルトブラウザ・`~/Downloads/` に保存 |
| `-e`, `--edit` | 編集モード: バックグラウンドサーバー + ブラウザライブエディタ（`-t` と組み合わせで TUI エディタ） |
| `-s`, `--settings` | TUI 設定画面を開く（単独フラグ） |
| `--update` | git から最新版を取得して依存関係を更新 |
| `--help-ja` | 日本語ヘルプを表示 |
| `--help-en` | 英語ヘルプを表示 |
| `--version` | バージョンを表示 |

---

## 対応ファイル形式

| 拡張子 | ブラウザモード | TUI モード |
|--------|---------------|-----------|
| `.md` `.markdown` | Markdown レンダリング（コードブロック・表・チェックリスト対応） | Markdown レンダリング |
| `.txt` | 行番号付きプレーンテキスト | 行番号付きプレーンテキスト |
| `.pdf` | ブラウザのネイティブ PDF ビューア | pdftotext でテキスト抽出（要 poppler-utils） |
| `.png` `.jpg` `.jpeg` `.gif` `.webp` `.svg` | 画像を直接表示 | chafa でターミナルプレビュー（要 chafa） |
| `.csv` `.tsv` | ソート可能なテーブル表示 | テキスト表形式 |
| `.py` `.js` `.ts` `.html` `.css` `.go` `.rs` `.json` `.yaml` ... | シンタックスハイライト表示（40以上の言語） | Rich でシンタックスハイライト |
| `.diff` `.patch` | 差分シンタックスハイライト | Rich でシンタックスハイライト |

> **TUI で PDF を表示:** `sudo apt install poppler-utils`（Linux / WSL）/ `brew install poppler`（macOS）  
> **TUI で画像を表示:** `sudo apt install chafa`（Linux / WSL）/ `brew install chafa`（macOS）

---

## peak コマンド

`peek` を `peak` と打ち間違えると、折れ線グラフが左から右へ伸びて頂点（★）に達するアニメーションが表示されます。  
`sl` と `ls` と同じ立場のコマンドです。

```bash
peak            # グラフアニメーションを表示
peak -v         # バージョンを表示（peak --version も同様）
```

> 既に `peak` という別コマンドがインストールされている場合はスキップされます。

---

## サーバーの停止

**通常ブラウザモード (`peek file.md`):**  
ターミナルで `Ctrl+C` を押すとサーバーが終了します。

**編集モード (`peek -e file.md`):**  
起動時に表示された PID で停止します。

```
peek: README.md  [Windows] [edit]
      http://localhost:8899/?token=***
      PID 12345 — kill 12345 to stop
```

```bash
kill 12345
```

**TUI モード (`peek -t file.md`):**  
設定した終了キー（デフォルト: `Ctrl+Q`）で終了します。

---

## アップデート

新しいバージョンがリリースされたら、以下のコマンド一つで更新できます。

```bash
peek --update
```

`git pull` でコードを取得し、依存関係も自動で更新します。

---

## 仕組み

**ブラウザモード（デフォルト）:**
1. Flask がローカルサーバーを起動（ポート 8899〜8999 を自動選択）
2. OS を自動検出して適切なコマンドでブラウザを開く
   - WSL: `cmd.exe /c start <URL>` または `wslview`
   - Linux: `xdg-open` / `firefox` / `chromium` など
   - macOS: `open <URL>`
3. `.md` は markdown2 でサーバーサイドレンダリング
4. アクセストークンによるセッション認証でローカル外からのアクセスを防止
5. DOMPurify（クライアントサイド）+ HTML サニタイザー（サーバーサイド）で XSS を防止

**TUI モード (`-t`):**
1. textual がターミナル上に直接レンダリング
2. `.md` は Markdown ウィジェットでレンダリング、`.txt` は行番号付きスクロール表示
3. `.pdf` は pdftotext でテキスト抽出して表示（未インストールの場合はブラウザ案内）
4. 画像は chafa でターミナルプレビュー（未インストールの場合はブラウザ案内）
5. `.csv` / `.tsv` はデリミタを自動検出してテキスト表形式で表示
6. `peek -s` で設定したテーマ・カラー・フォント・キーバインドを反映

WSLg は不要です。

---

## 依存関係

- Python 3.8+
- [Flask](https://flask.palletsprojects.com/) — ローカル HTTP サーバー
- [markdown2](https://github.com/trentm/python-markdown2) — Markdown レンダリング
- [WeasyPrint](https://weasyprint.org/) — HTML → PDF 変換（PDF 生成機能用）
- [textual](https://github.com/Textualize/textual) — TUI フレームワーク（`-t` / `-s` モード用）

セットアップスクリプトが仮想環境を作成し自動でインストールします。  
PDF 生成は [pandoc](https://pandoc.org/) が入っていれば優先的に使用されます。

---

## 注意事項

**`peek` だけ打ったら何も起きない / エラーになる**

ファイルパスが必要です。使い方の概要が表示されます。

```
$ peek
peek 1.18.x  —  ファイルビューア for WSL / Linux / macOS

  使い方: peek [オプション] <ファイル>

    peek README.md          ブラウザで開く（デフォルト）
    peek -t README.md       TUI で開く
    peek -t -e README.md    TUI エディタ（リアルタイムプレビュー）
    peek -e README.md       ブラウザライブエディタ
    peek -s                 設定（テーマ・カラー・フォント・キーバインド）

  詳細: peek --help-ja  /  peek --help-en
```

**`peek -list` など存在しないオプションを指定した**

不明なオプションはエラーになり、近いコマンドを提案します（もしかして？）。

```
$ peek -tui README.md
peek: 不明なオプション '-tui'
      もしかして: --tui
      詳細: peek --help-ja  /  peek --help-en
```

**`peek: command not found` と表示される**

PATH が通っていません。以下を実行してください。

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

**ブラウザが自動で開かない**

ターミナルに表示された URL を手動でブラウザに貼り付けてください。

```
peek: README.md  [Windows]
      http://localhost:8899/?token=***   ← これをブラウザのアドレスバーに入力
      Ctrl+C to close
```

**PDF を TUI で表示したい**

`pdftotext` が必要です。

```bash
sudo apt install poppler-utils   # WSL / Linux
brew install poppler             # macOS
```

**画像を TUI で表示したい**

`chafa` が必要です。

```bash
sudo apt install chafa   # WSL / Linux
brew install chafa       # macOS
```

**ポートが毎回変わる**

8899〜8999 の範囲で空いているポートを自動選択するため、起動のたびに変わる場合があります。  
ターミナルに表示された URL を使ってください。

---

## バグ報告・機能追加の要望

GitHub Issues からお気軽にどうぞ。

- **バグ報告・機能追加:** [github.com/s-lifecore/peek/issues](https://github.com/s-lifecore/peek/issues)

---

## ライセンス

[MIT License](LICENSE)

## 作成者

- 作者: [s-lifecore](https://github.com/s-lifecore)
