---
name: figma-import
type: knowledge
version: 1.0.0
agent: CodeActAgent
triggers:
- figma
- design file
- mockup
- wireframe
- design tokens
- import design
- from figma
- design reference
---

# Figma Import — Design-to-Code Pipeline

Extract design tokens and structure from Figma files and convert to code.

## Option 1: Figma MCP Server (Recommended)

If the Figma MCP server is available, use it directly:

```bash
# The MCP server provides these tools:
# - get_design_context: Get component structure and layout
# - get_screenshot: Capture a visual reference
# - get_variable_defs: Extract design tokens (colors, spacing, fonts)
# - get_metadata: Get file info and pages
```

### Workflow with Figma MCP:

```
1. User provides Figma URL
2. Call get_metadata to understand the file structure
3. Call get_variable_defs to extract design tokens:
   - Colors → map to Tailwind/shadcn theme
   - Typography → map to Tailwind text scale
   - Spacing → verify against 8px grid
4. Call get_screenshot for each key frame/page
5. Call get_design_context for component structure
6. Generate code following the design system skill
7. Compare screenshots against Figma reference
```

## Option 2: Manual Design Token Extraction

If the user provides a screenshot or describes their Figma design:

### Extract These Tokens:

```typescript
// design-tokens.ts
export const tokens = {
  colors: {
    primary: '#...', // Main brand color
    secondary: '#...', // Supporting color
    background: '#...', // Page background
    surface: '#...', // Card/component background
    text: '#...', // Primary text
    textMuted: '#...', // Secondary text
    border: '#...', // Border color
    accent: '#...', // Highlight/accent
  },
  typography: {
    fontFamily: 'Inter, sans-serif',
    h1: { size: '48px', weight: 700, lineHeight: 1.1 },
    h2: { size: '32px', weight: 600, lineHeight: 1.2 },
    h3: { size: '24px', weight: 600, lineHeight: 1.3 },
    body: { size: '16px', weight: 400, lineHeight: 1.6 },
    small: { size: '14px', weight: 400, lineHeight: 1.5 },
  },
  spacing: {
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
    xl: '32px',
    '2xl': '48px',
    '3xl': '64px',
    section: '80px',
  },
  borderRadius: {
    sm: '4px',
    md: '8px',
    lg: '12px',
    xl: '16px',
    full: '9999px',
  },
};
```

### Map to Tailwind Config:

```javascript
// tailwind.config.js (extend)
module.exports = {
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f0f9ff',
          100: '#e0f2fe',
          500: '#3b82f6', // from Figma primary
          600: '#2563eb',
          700: '#1d4ed8',
        },
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
    },
  },
};
```

### Map to shadcn Theme:

```css
/* src/index.css - update CSS variables */
@layer base {
  :root {
    --background: 0 0% 100%;           /* from Figma background */
    --foreground: 222 47% 11%;         /* from Figma text */
    --primary: 221 83% 53%;           /* from Figma primary */
    --primary-foreground: 210 40% 98%;
    --secondary: 210 40% 96%;
    --muted: 210 40% 96%;
    --muted-foreground: 215 16% 47%;
    --border: 214 32% 91%;
    --radius: 0.5rem;                  /* from Figma borderRadius */
  }
}
```

## Figma → Component Mapping

| Figma Element | React Component |
|--------------|----------------|
| Rectangle with text | `<Card>` or `<Button>` |
| Text layer | `<h1>`, `<p>`, or `<span>` with Tailwind classes |
| Frame with auto-layout | `<div className="flex">` or `grid` |
| Icon | Lucide React icon (find closest match) |
| Input field | shadcn `<Input>` |
| Dropdown | shadcn `<Select>` |
| Toggle | shadcn `<Switch>` |
| Modal/Dialog | shadcn `<Dialog>` |
| Navigation | `<header>` with flex layout |

## Figma Auto-Layout → Tailwind Flex/Grid

| Figma Property | Tailwind Equivalent |
|---------------|-------------------|
| Auto layout: Horizontal | `flex flex-row` |
| Auto layout: Vertical | `flex flex-col` |
| Gap: 16 | `gap-4` |
| Padding: 24 | `p-6` |
| Fill container | `w-full` or `flex-1` |
| Hug contents | `w-fit` |
| Space between | `justify-between` |
| Center aligned | `items-center` |

## Process for Figma-to-Code

```
1. ANALYZE the design
   - Count distinct sections
   - Identify repeated patterns (cards, list items)
   - Note the color palette
   - Note typography sizes used

2. EXTRACT tokens
   - Map colors to shadcn CSS variables
   - Map fonts to Tailwind config
   - Map spacing to 8px grid

3. BUILD component-by-component
   - Start with layout (container, grid, flex)
   - Add typography
   - Add colors
   - Add interactive states (hover, focus)

4. VERIFY against reference
   - Screenshot the built page
   - Compare with Figma screenshot
   - Fix discrepancies
```
