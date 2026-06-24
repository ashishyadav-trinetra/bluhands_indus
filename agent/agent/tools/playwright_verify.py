"""Playwright self-test tool — the agent's "did it actually work?" gate.

Drives the running preview with a headless browser, exercises the critical flows
declared in the capability manifest, captures screenshots, and returns a
structured pass/fail the agent can read and act on.

Playwright is imported lazily so this module imports without it; ``verify`` is
only invoked during a real build.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class VerifyResult:
    """Outcome of a verification pass."""

    passed: bool
    checked: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    screenshots: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if self.passed:
            return f"PASS — {len(self.checked)} flow(s) verified."
        return f"FAIL — {len(self.failures)} issue(s): " + "; ".join(self.failures)


async def verify(
    preview_url: str,
    *,
    critical_flows: list[str],
    screenshot_dir: str | Path | None = None,
) -> VerifyResult:
    """Open ``preview_url`` and assert each critical flow renders without errors.

    Phase T-A01 implements the harness + a baseline check (page loads, no console
    errors, body has content, screenshot captured per flow). Flow-specific
    assertions (apply filter, add to cart, checkout) are layered in T-A07 once a
    real storefront + manifest exist.

    Raises:
        RuntimeError: if Playwright is not installed.
    """
    try:
        from playwright.async_api import async_playwright  # type: ignore
    except ImportError as exc:  # pragma: no cover - needs playwright
        raise RuntimeError("playwright is not installed; run `pip install playwright`.") from exc

    out_dir = Path(screenshot_dir) if screenshot_dir else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
    result = VerifyResult(passed=True)
    flows = critical_flows or ["page_load"]

    async with async_playwright() as p:  # pragma: no cover - needs a browser
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        console_errors: list[str] = []
        page.on(
            "console",
            lambda m: console_errors.append(m.text) if m.type == "error" else None,
        )
        try:
            for flow in flows:
                await page.goto(preview_url, wait_until="networkidle", timeout=30_000)
                if out_dir:
                    shot = out_dir / f"{flow}.png"
                    await page.screenshot(path=str(shot), full_page=True)
                    result.screenshots.append(str(shot))
                body = await page.inner_text("body")
                if not body.strip():
                    result.failures.append(f"{flow}: empty page body")
                result.checked.append(flow)
            if console_errors:
                result.failures.append(f"console errors: {console_errors[:3]}")
        finally:
            await browser.close()

    result.passed = not result.failures
    return result
