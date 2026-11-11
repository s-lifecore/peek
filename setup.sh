#!/bin/bash
set -e

INSTALL_DIR="$HOME/.local/bin"
VENV_DIR="$HOME/.local/share/peek-venv"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "peek: Creating Python virtual environment..."
python3 -m venv "$VENV_DIR"

echo "peek: Installing dependencies..."
"$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" --quiet

echo "peek: Configuring git hooks..."
git -C "$SCRIPT_DIR" config core.hooksPath .githooks

echo "peek: Installing CLI command..."
mkdir -p "$INSTALL_DIR"

cat > "$INSTALL_DIR/peek" << EOF
#!/bin/bash
exec "$VENV_DIR/bin/python" "$SCRIPT_DIR/peek.py" "\$@"
EOF

chmod +x "$INSTALL_DIR/peek"

# Install 'peak' script unless another command already owns it
EXISTING_PEAK="$(command -v peak 2>/dev/null || true)"
if [[ -n "$EXISTING_PEAK" && "$EXISTING_PEAK" != "$INSTALL_DIR/peak" ]]; then
  echo "peek: 'peak' コマンドが既に存在するためスキップしました: $EXISTING_PEAK"
else
  # Remove any existing symlink before writing (avoid overwriting symlink target)
  rm -f "$INSTALL_DIR/peak"
  cat > "$INSTALL_DIR/peak" << EOF
#!/bin/bash
if [[ "\$1" == "-v" || "\$1" == "--version" ]]; then
  exec "$VENV_DIR/bin/python" "$SCRIPT_DIR/peek.py" --version
fi
exec "$VENV_DIR/bin/python" "$SCRIPT_DIR/peek.py" --peak
EOF
  chmod +x "$INSTALL_DIR/peak"
  echo "peek: 'peak' コマンドもインストールしました。"
fi

echo ""
echo "Done!  'peek' command installed."
echo ""

if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
  echo "Add the following to your ~/.bashrc to use 'peek' from anywhere:"
  echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
  echo ""
  echo "Then reload: source ~/.bashrc"
  echo ""
fi

echo "Try it: peek --help-ja"
