"""Deterministic brand application — no LLM required.

The merchant's brand kit (hex colors) is written straight into the storefront's
design tokens (``app/globals.css``), which everything themes off (ADR-4). This
guarantees the store is correctly branded even if the AI customization step is
skipped or fails — the LLM only *enhances* on top of a known-good result.

Pure functions (``hex_to_hsl``, ``css_var_line``) are unit-tested; ``apply_brand``
is a thin file edit on top of them.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def hex_to_hsl(hex_color: str) -> tuple[int, int, int]:
    """Convert ``#rrggbb`` (or ``#rgb``) to integer (H, S%, L%).

    Returns hue in [0,360], saturation/lightness in [0,100].
    Raises ValueError on malformed input.
    """
    h = hex_color.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6 or not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        raise ValueError(f"invalid hex color: {hex_color!r}")

    r, g, b = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))
    mx, mn = max(r, g, b), min(r, g, b)
    light = (mx + mn) / 2

    if mx == mn:
        hue = sat = 0.0
    else:
        delta = mx - mn
        sat = delta / (2 - mx - mn) if light > 0.5 else delta / (mx + mn)
        if mx == r:
            hue = (g - b) / delta + (6 if g < b else 0)
        elif mx == g:
            hue = (b - r) / delta + 2
        else:
            hue = (r - g) / delta + 4
        hue /= 6

    return round(hue * 360), round(sat * 100), round(light * 100)


def _triplet(hex_color: str) -> str:
    """Render a hex color as the ``H S% L%`` string shadcn tokens expect."""
    hh, ss, ll = hex_to_hsl(hex_color)
    return f"{hh} {ss}% {ll}%"


def _readable_foreground(hex_color: str) -> str:
    """Pick black or white foreground for contrast against ``hex_color``."""
    _, _, light = hex_to_hsl(hex_color)
    return "0 0% 100%" if light < 60 else "222 47% 11%"


def css_var_line(name: str, value: str) -> str:
    """Return a single CSS custom-property declaration line."""
    return f"    --{name}: {value};"


def apply_brand(workspace: Path | str, brand: dict[str, Any]) -> Path:
    """Rewrite the storefront's color tokens from the brand kit.

    Updates ``--primary``/``--primary-foreground`` and adds/updates an
    ``--accent`` token. Returns the edited globals.css path. No-op (returns the
    path) if there's nothing to apply.

    Raises:
        FileNotFoundError: if app/globals.css is missing.
    """
    workspace = Path(workspace)
    css_path = workspace / "app" / "globals.css"
    if not css_path.is_file():
        raise FileNotFoundError(f"globals.css not found: {css_path}")

    primary = brand.get("primaryColor")
    accent = brand.get("accentColor")
    css = css_path.read_text(encoding="utf-8")

    if primary:
        css = _set_var(css, "primary", _triplet(primary))
        css = _set_var(css, "primary-foreground", _readable_foreground(primary))
    if accent:
        css = _set_var(css, "accent", _triplet(accent))
        css = _set_var(css, "accent-foreground", _readable_foreground(accent))

    css_path.write_text(css, encoding="utf-8")
    return css_path


def _set_var(css: str, name: str, value: str) -> str:
    """Replace an existing ``--name: ...;`` declaration, or insert it under :root."""
    pattern = re.compile(rf"(--{re.escape(name)}\s*:\s*)[^;]+;")
    if pattern.search(css):
        return pattern.sub(rf"\g<1>{value};", css, count=1)
    # Insert right after the first ``:root {`` block opener.
    return re.sub(r"(:root\s*\{\s*\n)", rf"\1{css_var_line(name, value)}\n", css, count=1)
