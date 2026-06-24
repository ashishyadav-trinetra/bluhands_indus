"""Unit tests for deterministic brand application."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.brand import apply_brand, css_var_line, hex_to_hsl

_GLOBALS = """@tailwind base;
@layer base {
  :root {
    --background: 0 0% 100%;
    --primary: 222 47% 31%;
    --primary-foreground: 0 0% 100%;
    --radius: 0.6rem;
  }
}
"""


def test_hex_to_hsl_known_values() -> None:
    assert hex_to_hsl("#ffffff") == (0, 0, 100)
    assert hex_to_hsl("#000000") == (0, 0, 0)
    # Pure red -> hue 0, full saturation, mid lightness.
    assert hex_to_hsl("#ff0000") == (0, 100, 50)
    # Shorthand expands.
    assert hex_to_hsl("#fff") == (0, 0, 100)


def test_hex_to_hsl_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        hex_to_hsl("not-a-color")


def test_css_var_line_format() -> None:
    assert css_var_line("accent", "10 20% 30%") == "    --accent: 10 20% 30%;"


def test_apply_brand_replaces_primary_and_inserts_accent(tmp_path: Path) -> None:
    ws = tmp_path
    (ws / "app").mkdir()
    css_file = ws / "app" / "globals.css"
    css_file.write_text(_GLOBALS, encoding="utf-8")

    apply_brand(ws, {"primaryColor": "#ff0000", "accentColor": "#00ff00"})
    out = css_file.read_text(encoding="utf-8")

    # Primary replaced with red's HSL; light red -> white foreground stays.
    assert "--primary: 0 100% 50%;" in out
    # Accent did not exist -> inserted under :root.
    assert "--accent: 120 100% 50%;" in out
    # Untouched tokens survive.
    assert "--background: 0 0% 100%;" in out


def test_apply_brand_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        apply_brand(tmp_path, {"primaryColor": "#123456"})
