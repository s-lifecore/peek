#!/usr/bin/env python3
"""peek validation: syntax + Textual static CSS check."""
import ast
import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
PEEK_PY = os.path.join(ROOT, "peek.py")


def check_syntax() -> str:
    with open(PEEK_PY) as f:
        source = f.read()
    try:
        ast.parse(source)
        print("✓ syntax")
        return source
    except SyntaxError as e:
        print(f"✗ syntax: {e}")
        sys.exit(1)


def check_css(source: str) -> None:
    """Validate static CSS = '...' class attributes using Textual's own parser."""
    try:
        import asyncio
        from textual.app import App, ComposeResult
        from textual.widgets import Label
    except ImportError:
        print("⚠ textual not installed — CSS check skipped")
        return

    # Extract only non-f-string CSS = "..." class attributes
    tree = ast.parse(source)
    css_blocks: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.Assign):
                    for t in item.targets:
                        if isinstance(t, ast.Name) and t.id == "CSS":
                            if isinstance(item.value, ast.Constant) and isinstance(item.value.value, str):
                                css_blocks.append((node.name, item.value.value))

    if not css_blocks:
        print("⚠ no static CSS blocks found — CSS check skipped")
        return

    async def _run(css: str, name: str) -> bool:
        class _T(App):
            CSS = css

            def compose(self) -> ComposeResult:
                yield Label("")

        try:
            async with _T().run_test(headless=True, size=(80, 24)) as pilot:
                await pilot.exit(0)
            print(f"✓ CSS  {name}")
            return True
        except Exception as e:
            print(f"✗ CSS  {name}: {e}")
            return False

    async def _all() -> bool:
        return all([await _run(css, name) for name, css in css_blocks])

    ok = asyncio.run(_all())
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    print("peek: running checks")
    source = check_syntax()
    check_css(source)
    print("\nAll checks passed.")
