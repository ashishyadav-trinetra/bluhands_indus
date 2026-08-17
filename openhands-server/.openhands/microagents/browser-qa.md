---
name: browser-qa
type: knowledge
version: 1.0.0
agent: CodeActAgent
triggers:
- check the page
- screenshot
- test the UI
- visual test
- verify
- does it look
- inspect
- QA
---

# Browser QA — Visual Testing Process

When you need to verify your work visually, use the browser tools.

## Step 1: Start the Server

```bash
# Make sure the server is running
npx vite --host 0.0.0.0 --port $APP_PORT &
# Wait a moment for it to start
sleep 3
```

## Step 2: Navigate and Screenshot

Use the browser tools:
```
browser_navigate: {"url": "http://localhost:$APP_PORT"}
browser_get_state: {}
```

This gives you the page content. Inspect the DOM structure for:

## Step 3: Automated Checks

After seeing the page content, verify:

### Structure Check
- [ ] `<header>` exists with navbar content
- [ ] `<main>` or content sections exist
- [ ] `<footer>` exists
- [ ] Sections have consistent max-width containers

### Typography Check
- [ ] H1 exists and is the largest text element
- [ ] Only ONE H1 per page
- [ ] H2s are used for section titles
- [ ] Body text uses appropriate size

### Layout Check
- [ ] Grid layouts use responsive breakpoints
- [ ] Cards are in a grid, not stacked singly
- [ ] Hero section has adequate vertical padding
- [ ] Content doesn't touch screen edges (has padding)

### Component Check
- [ ] Buttons have proper variant styling
- [ ] Cards have consistent padding
- [ ] Icons are appropriately sized (16-24px)
- [ ] Forms have labels and proper spacing

## Step 4: Fix and Re-verify

If any check fails:
1. Fix the specific issue
2. Save the file
3. Navigate to the page again
4. Re-run the checks
5. Don't stop until ALL checks pass

## Step 5: Functional Testing (CRITICAL)

After visual checks pass, test EVERY interactive element:

```
# Click each button and verify it does something
# Type in search bars and verify filtering works
# Open dropdowns/modals and verify they open AND close
# Submit forms and verify success/error states
# Check that empty states show helpful messages
```

| Test | Expected | If Broken |
|------|----------|-----------|
| Click a button | Visible action (navigate, open modal, submit) | Add proper onClick handler |
| Type in search | List filters in real-time | Add useState + onChange + filter logic |
| Click filter/sort | Data reorders/filters | Add state + useMemo for derived data |
| Open dropdown | Menu appears with options | Use shadcn DropdownMenu, not custom div |
| Submit form | Loading state → success message | Add form state management |
| View empty list | "No items found" message | Add empty state conditional |

## Common Issues to Watch For

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Content touching edges | Missing container | Add `max-w-6xl mx-auto px-4` |
| Everything same size | No hierarchy | Increase heading sizes, mute body text |
| Page feels empty | Not enough content | Add more sections, use feature grids |
| Page feels cramped | Not enough spacing | Increase section `py-*`, card `gap-*` |
| Broken on mobile | Missing responsive classes | Add `md:` and `lg:` breakpoints |
| Ugly buttons | Not using shadcn Button | Replace with `<Button>` component |
| Search bar does nothing | No state/filter logic | Add useState + onChange + useMemo filter |
| Button does nothing | Empty or missing onClick | Wire up proper event handler |
| Dropdown doesn't open | Custom div instead of shadcn | Replace with shadcn DropdownMenu |
| Form submits but nothing happens | No async handler | Add try/catch with loading + success state |
