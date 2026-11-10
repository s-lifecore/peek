# peek

WSL / Linux / macOS ターミナルから `.md` `.txt` `.pdf` をブラウザで開く CLI ビューアです。

```bash
peek README.md
```

コマンド一つで Markdown レンダリング・テキスト・PDF をブラウザで確認できます。  
OS は自動検出され、適切なブラウザが起動します。

---

## 特徴

- **Markdown レンダリング** — 見出し・表・コードブロック・チェックリストをきれいに表示
- **PDF ビューア** — ブラウザのネイティブ PDF ビューアでそのまま開く
- **テキスト表示** — 行番号付きで等幅フォント表示
- **PDF 生成** — `.md` から PDF を直接生成（pandoc / weasyprint 対応）
- **ライブ編集モード** — `-e` でサーバーをバックグラウンドに切り離し、ブラウザ上でリアルタイム編集
- **マルチプラットフォーム** — WSL / Linux / macOS を自動検出、フラグで明示指定も可能
- **ファイルダウンロード** — Windows はブラウザ経由、Linux / macOS は `~/Downloads/` に保存
- **セキュリティ** — アクセストークン認証、LFI 防止、セキュリティヘッダー付き

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

プラットフォームはフラグ未指定時に自動検出されます:  
`macOS → -m` | `WSL → -w` | `Linux → -l`

### 基本的な使い方

```bash
peek README.md          # Markdown をレンダリングして表示
peek notes.txt          # テキストファイルを表示
peek document.pdf       # PDF を表示
```

### プラットフォーム指定

```bash
peek -w README.md       # Windows のデフォルトブラウザで開く（WSL）
peek -l notes.txt       # Linux のデフォルトブラウザで開く
peek -m README.md       # macOS のデフォルトブラウザで開く
```

### 編集モード

```bash
peek -e README.md
```

サーバーをバックグラウンドに切り離し、ターミナルを解放します。  
ブラウザ上でリアルタイム編集・保存ができます（Markdown はプレビュー付き）。  
終了するにはターミナルに表示された PID を使って `kill <PID>` します。

---

## コマンドオプション

| オプション | 説明 |
|------------|------|
| `-w`, `--windows` | Windows のデフォルトブラウザで開く・Windows に保存 |
| `-l`, `--linux` | Linux のデフォルトブラウザで開く・`~/Downloads/` に保存 |
| `-m`, `--mac` | macOS のデフォルトブラウザで開く・`~/Downloads/` に保存 |
| `-e`, `--edit` | 編集モード: バックグラウンドサーバー + ライブエディタ |
| `--update` | git から最新版を取得して依存関係を更新 |
| `--help-ja` | 日本語ヘルプを表示 |
| `--help-en` | 英語ヘルプを表示 |
| `--version` | バージョンを表示 |

---

## 対応ファイル形式

| 拡張子 | 表示方法 |
|--------|----------|
| `.md` `.markdown` | Markdown レンダリング（コードブロック・表・チェックリスト対応） |
| `.txt` | 行番号付きプレーンテキスト表示 |
| `.pdf` | ブラウザのネイティブ PDF ビューア |

---

## サーバーの停止

**通常モード (`peek file.md`):**  
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

---

## アップデート

新しいバージョンがリリースされたら、以下のコマンド一つで更新できます。

```bash
peek --update
```

`git pull` でコードを取得し、依存関係も自動で更新します。

---

## 仕組み

1. `peek file.md` を実行すると Flask がローカルサーバーを起動
2. OS を自動検出して適切なコマンドでブラウザを開く  
   - WSL: `cmd.exe /c start <URL>` または `wslview`  
   - Linux: `xdg-open` / `firefox` / `chromium` など  
   - macOS: `open <URL>`
3. `.md` は markdown2 でサーバーサイドレンダリング、`.pdf` はブラウザネイティブビューアに委譲
4. アクセストークンによるセッション認証でローカル外からのアクセスを防止

WSLg は不要です。

---

## 依存関係

- Python 3.8+
- [Flask](https://flask.palletsprojects.com/) — ローカル HTTP サーバー
- [markdown2](https://github.com/trentm/python-markdown2) — Markdown レンダリング
- [WeasyPrint](https://weasyprint.org/) — HTML → PDF 変換（PDF 生成機能用）

セットアップスクリプトが仮想環境を作成し自動でインストールします。  
PDF 生成は [pandoc](https://pandoc.org/) が入っていれば優先的に使用されます。

---

## 注意事項

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

**ポートが毎回変わる**

8899〜8999 の範囲で空いているポートを自動選択するため、起動のたびに変わる場合があります。  
ターミナルに表示された URL を使ってください。

---

## ライセンス

[MIT License](LICENSE)

## 作成者

- 作者: [s-lifecore](https://github.com/s-lifecore)
