---
name: layout-critic
type: knowledge
version: 1.0.0
agent: CodeActAgent
triggers:
- review
- polish
- improve
- fix layout
- looks bad
- make it better
- cleanup
- refine
- professional
---

# Layout Critic — UI Quality Review Process

When the user asks you to review, polish, or improve a UI, follow this process strictly.

## Step 1: Run the App and Inspect

```bash
# Start the dev server
npx vite --host 0.0.0.0 --port 8011

# Open in browser tool to take a screenshot
browser_navigate http://localhost:8011
browser_get_content
```

## Step 2: Score Against This Rubric

For each section of the page, score 1-5 on:

| Criteria | What to check |
|----------|--------------|
| **Hierarchy** | Is there ONE clear focal point? Is the heading the largest element? |
| **Spacing** | Is the 8px grid followed? Are sections evenly spaced? No cramped areas? |
| **Alignment** | Are elements on a consistent grid? No floating orphans? |
| **Typography** | Max 2 font sizes per section? Muted body text? Tight heading tracking? |
| **CTA clarity** | Only ONE primary button per section? Secondary buttons use outline? |
| **Whitespace** | Enough breathing room? Hero section tall enough? Cards not jammed together? |
| **Responsiveness** | Would this work on mobile? Are grids stacking properly? |
| **Color consistency** | Using semantic colors (not hardcoded hex)? Muted foreground for body? |

## Step 3: Fix Issues (In Order of Impact)

1. **Spacing first** — Fix section padding, card gaps, component spacing
2. **Typography second** — Fix font sizes, weights, colors
3. **Layout third** — Fix grid columns, max-widths, alignment
4. **Color fourth** — Replace hardcoded colors with semantic tokens
5. **Polish last** — Add hover states, transitions, rounded corners

## Common Fixes

### "Everything looks flat / same size"
```
Problem: No visual hierarchy
Fix: Make heading text-4xl bold, subtext text-muted-foreground, increase section py-20
```

### "Cards look cramped"
```
Problem: Insufficient padding
Fix: Card padding p-6, gap-6 between cards, section py-16
```

### "Too many buttons fighting for attention"
```
Problem: Multiple primary CTAs
Fix: Keep ONE primary, make others variant="outline" or variant="ghost"
```

### "Page looks narrow / wide"
```
Problem: Missing max-width container
Fix: Add max-w-6xl mx-auto px-4 md:px-6 to every section
```

### "Text is hard to read"
```
Problem: White text on dark background without muting
Fix: Body text should be text-muted-foreground, not text-white
```

## Step 4: Verify Fix

After each fix:
1. Save the file
2. Wait for hot-reload
3. Take another screenshot
4. Compare against rubric
5. If score improved, move to next issue
6. If not, try a different approach

## The "3-Pass" Rule

Never stop after one pass. Do AT LEAST 3 passes:
- Pass 1: Structure (layout, grid, max-width, sections)
- Pass 2: Typography (sizes, weights, colors, spacing)
- Pass 3: Polish (hover states, transitions, icons, alignment)
