# peek

WSL ターミナルから `.md` `.txt` `.pdf` をブラウザで開く CLI ビューアです。

```bash
peek README.md
```

コマンド一つで、マークダウンのレンダリング・テキスト・PDF をブラウザで確認できます。  
nano や vim でファイルを開かなくても良くなります。

---

## 特徴

- **Markdown レンダリング** — 見出し・表・コードブロック・チェックリストをきれいに表示
- **PDF ビューア** — ブラウザのネイティブ PDF ビューアでそのまま開く
- **テキスト表示** — 等幅フォントで読みやすく表示
- **自動ブラウザ起動** — `cmd.exe` 経由で Windows ブラウザを自動で開く
- **ポート自動選択** — 8899 が塞がっていても自動で空きポートを探す
- **日英ヘルプ** — `--help-ja` / `--help-en` で言語切替

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

**Bash の場合:**
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

**Zsh の場合:**
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
peek <ファイル>
```

### 例

```bash
peek README.md          # マークダウンをレンダリングして表示
peek notes.txt          # テキストファイルを表示
peek document.pdf       # PDF を表示
```

ブラウザが開いたら、ターミナルで `Ctrl+C` を押してサーバーを終了します。

---

## 対応ファイル形式

| 拡張子 | 表示方法 |
|--------|----------|
| `.md` `.markdown` | Markdown レンダリング（コードブロック・表・チェックリスト対応） |
| `.txt` | 等幅フォントでプレーンテキスト表示 |
| `.pdf` | ブラウザのネイティブ PDF ビューア |

---

## コマンドオプション

| オプション | 説明 |
|------------|------|
| `--help-ja` | 日本語ヘルプを表示 |
| `--help-en` | 英語ヘルプを表示 |
| `--version` | バージョンを表示 |

---

## 仕組み

1. `peek file.md` を実行すると Flask がローカルサーバーを起動
2. `cmd.exe /c start http://localhost:PORT` で Windows ブラウザを自動で開く
3. `.md` は markdown2 でサーバーサイドレンダリング、`.pdf` はブラウザのネイティブビューアに委譲
4. `Ctrl+C` でサーバーを終了

WSLg は不要です。Windows ブラウザをそのまま使います。

---

## 依存関係

- Python 3.8+
- [Flask](https://flask.palletsprojects.com/) — ローカル HTTP サーバー
- [markdown2](https://github.com/trentm/python-markdown2) — Markdown レンダリング

セットアップスクリプトが仮想環境を作成し自動でインストールします。

---

## ライセンス

[MIT License](LICENSE)

## 作成者

- 作成日: 2025年11月
- バージョン: 1.0.0
- 作者: [s-lifecore](https://github.com/s-lifecore)
