---
name: screenshot-comparison
type: knowledge
version: 1.0.0
agent: CodeActAgent
triggers:
- screenshot
- compare
- pixel
- visual test
- looks like
- match
- reference
- screenshot diff
- visual comparison
- check UI
- verify layout
---

# Screenshot Comparison — Visual Regression Testing

Use Playwright to capture screenshots, compare against references, and iterate until the UI matches.

## Setup (Run Once Per Project)

```bash
npm install -D @playwright/test
npx playwright install chromium
```

## Create the Screenshot Script

Create `scripts/screenshot.mjs` in the project:

```javascript
import { chromium } from 'playwright';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs';
import { join } from 'path';

const SCREENSHOT_DIR = './screenshots';
const URL = process.argv[2] || 'http://localhost:8011';
const NAME = process.argv[3] || 'page';

if (!existsSync(SCREENSHOT_DIR)) mkdirSync(SCREENSHOT_DIR, { recursive: true });

async function capture() {
  const browser = await chromium.launch();

  // Desktop screenshot
  const desktopPage = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await desktopPage.goto(URL, { waitUntil: 'networkidle' });
  await desktopPage.waitForTimeout(1000); // Wait for animations
  await desktopPage.screenshot({
    path: join(SCREENSHOT_DIR, `${NAME}-desktop.png`),
    fullPage: true,
  });

  // Mobile screenshot
  const mobilePage = await browser.newPage({ viewport: { width: 375, height: 812 } });
  await mobilePage.goto(URL, { waitUntil: 'networkidle' });
  await mobilePage.waitForTimeout(1000);
  await mobilePage.screenshot({
    path: join(SCREENSHOT_DIR, `${NAME}-mobile.png`),
    fullPage: true,
  });

  // Tablet screenshot
  const tabletPage = await browser.newPage({ viewport: { width: 768, height: 1024 } });
  await tabletPage.goto(URL, { waitUntil: 'networkidle' });
  await tabletPage.waitForTimeout(1000);
  await tabletPage.screenshot({
    path: join(SCREENSHOT_DIR, `${NAME}-tablet.png`),
    fullPage: true,
  });

  await browser.close();

  console.log(`Screenshots saved to ${SCREENSHOT_DIR}/`);
  console.log(`  ${NAME}-desktop.png (1280x800)`);
  console.log(`  ${NAME}-mobile.png (375x812)`);
  console.log(`  ${NAME}-tablet.png (768x1024)`);
}

capture().catch(console.error);
```

## Create the Comparison Script

Create `scripts/compare-screenshots.mjs`:

```javascript
import { chromium } from 'playwright';
import { existsSync, readFileSync, writeFileSync } from 'fs';
import { join } from 'path';
import { createHash } from 'crypto';

const SCREENSHOT_DIR = './screenshots';

// Simple perceptual comparison using image hash
// Returns a similarity score 0-100 (100 = identical)
function compareImages(path1, path2) {
  if (!existsSync(path1) || !existsSync(path2)) {
    return { score: 0, error: 'File not found' };
  }

  const buf1 = readFileSync(path1);
  const buf2 = readFileSync(path2);

  // Size comparison (rough proxy)
  const sizeDiff = Math.abs(buf1.length - buf2.length) / Math.max(buf1.length, buf2.length);

  // Hash comparison
  const hash1 = createHash('md5').update(buf1).digest('hex');
  const hash2 = createHash('md5').update(buf2).digest('hex');

  if (hash1 === hash2) return { score: 100, identical: true };

  // Rough similarity based on file size proximity
  const score = Math.round((1 - sizeDiff) * 100);
  return { score, identical: false };
}

const before = process.argv[2] || 'before';
const after = process.argv[3] || 'after';

['desktop', 'mobile', 'tablet'].forEach(viewport => {
  const path1 = join(SCREENSHOT_DIR, `${before}-${viewport}.png`);
  const path2 = join(SCREENSHOT_DIR, `${after}-${viewport}.png`);

  if (existsSync(path1) && existsSync(path2)) {
    const result = compareImages(path1, path2);
    console.log(`${viewport}: ${result.score}% similar ${result.identical ? '(IDENTICAL)' : ''}`);
  } else {
    console.log(`${viewport}: Missing reference (${existsSync(path1) ? 'has before' : 'no before'}, ${existsSync(path2) ? 'has after' : 'no after'})`);
  }
});
```

## The Visual Iteration Loop

### Step 1: Capture "before" baseline
```bash
node scripts/screenshot.mjs http://localhost:8011 before
```

### Step 2: Make changes to the code
(Edit components, fix spacing, improve typography)

### Step 3: Capture "after"
```bash
node scripts/screenshot.mjs http://localhost:8011 after
```

### Step 4: Compare
```bash
node scripts/compare-screenshots.mjs before after
```

### Step 5: Evaluate
- If similarity < 95% after a fix → the change was significant, verify visually
- If similarity > 99% → the fix was too minor, look for bigger improvements
- Always capture desktop, mobile, AND tablet

## Playwright Visual Test (For CI/CD)

Create `tests/visual.spec.ts`:

```typescript
import { test, expect } from '@playwright/test';

test('homepage visual regression', async ({ page }) => {
  await page.goto('http://localhost:8011');
  await page.waitForLoadState('networkidle');

  // Full page screenshot comparison
  await expect(page).toHaveScreenshot('homepage.png', {
    maxDiffPixelRatio: 0.05, // Allow 5% pixel difference
    fullPage: true,
  });
});

test('homepage mobile', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('http://localhost:8011');
  await page.waitForLoadState('networkidle');

  await expect(page).toHaveScreenshot('homepage-mobile.png', {
    maxDiffPixelRatio: 0.05,
    fullPage: true,
  });
});
```

Run: `npx playwright test --update-snapshots` (first time to save references)
Then: `npx playwright test` (subsequent runs compare against references)

## When to Use Screenshots in the Build Loop

```
Phase 3 (Build): Write code
Phase 4 (Run): Start server
Phase 5 (Inspect):
    ├── Take desktop screenshot
    ├── Take mobile screenshot
    ├── Check: Does it have proper hierarchy? Spacing? Typography?
    ├── If NO → fix and re-screenshot
    └── If YES → proceed to polish
Phase 7 (Polish):
    ├── Take "before polish" screenshot
    ├── Add hover states, transitions, subtle improvements
    ├── Take "after polish" screenshot
    └── Compare: Should be visibly better but structurally similar
```
