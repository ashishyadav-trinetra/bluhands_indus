---
name: opinionated-stack
type: knowledge
version: 1.0.0
agent: CodeActAgent
triggers:
- tech stack
- what library
- which framework
- shadcn
- tailwind setup
---

# Opinionated Stack — Zero Decisions Mode

This skill removes ALL technology choices. You do NOT ask the user what to use. You ALWAYS use this exact stack.

## The Stack (Non-Negotiable)

| Layer | Technology | Why |
|-------|-----------|-----|
| Framework | React 18+ with TypeScript | Industry standard, typed |
| Build | Vite | Fastest bundler |
| Styling | Tailwind CSS v4 | Utility-first, no CSS files |
| Components | shadcn/ui | Editable, consistent, accessible |
| Icons | Lucide React | Tree-shakeable, consistent style |
| Font | Inter via Google Fonts | Clean, professional, free |
| Router | React Router v6 | Standard for SPAs |
| Animation | Framer Motion (sparingly) | Smooth, declarative |
| Forms | React Hook Form + Zod | Validated, typed |
| State | React useState/useReducer | Keep it simple |
| HTTP | fetch or axios | No exotic libraries |

## NEVER Use These

| Don't Use | Use Instead | Why |
|-----------|-------------|-----|
| CSS Modules | Tailwind classes | Consistency |
| styled-components | Tailwind classes | Bundle size |
| Material UI | shadcn/ui | Customizability |
| Ant Design | shadcn/ui | Opinionated styling |
| Bootstrap | Tailwind + shadcn | Modern look |
| Font Awesome | Lucide React | Consistent weight |
| Heroicons | Lucide React | More comprehensive |
| moment.js | date-fns or native | Bundle size |
| Redux | useState/useReducer | Simplicity |
| jQuery | Native DOM / React | It's 2026 |
| Raw `<button>` | shadcn `<Button>` | Consistency |
| Raw `<input>` | shadcn `<Input>` | Consistency |
| Custom modals | shadcn `<Dialog>` | Accessibility |
| Custom dropdowns | shadcn `<Select>` | Accessibility |

## Scaffold Command (Copy-Paste Every Time)

```bash
# Project init
npm create vite@latest . -- --template react-ts
npm install

# Tailwind
npm install -D tailwindcss @tailwindcss/vite

# shadcn/ui
npx shadcn@latest init -d

# Core shadcn components (install all of these)
npx shadcn@latest add button card input label textarea badge separator \
  avatar tabs tooltip dialog sheet dropdown-menu select switch checkbox \
  table skeleton alert

# Icons
npm install lucide-react

# Router
npm install react-router-dom

# Animation (optional)
npm install framer-motion

# Forms (if needed)
npm install react-hook-form @hookform/resolvers zod
```

## Tailwind Config

```typescript
// vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'path';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 8011,
  },
});
```

## Font Setup

```html
<!-- index.html -->
<head>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
</head>
```

```css
/* src/index.css - add to existing */
body {
  font-family: 'Inter', sans-serif;
}
```

## The cn() Helper (Already from shadcn init)

```typescript
// src/lib/utils.ts
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

Use `cn()` to merge Tailwind classes conditionally:
```tsx
<div className={cn("p-4 rounded-lg", isActive && "bg-primary text-primary-foreground")}>
```

## Import Conventions

```tsx
// Always use @ alias
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { ArrowRight, Star, Check } from 'lucide-react';
import { cn } from '@/lib/utils';
```

## File Naming

- Components: `PascalCase.tsx` (e.g., `HeroSection.tsx`)
- Pages: `PascalCase.tsx` (e.g., `AboutPage.tsx`)
- Utilities: `camelCase.ts` (e.g., `formatDate.ts`)
- Types: `camelCase.ts` in `types/` folder

## Server Start (ALWAYS)

```bash
npx vite --host 0.0.0.0 --port 8011
```

Or in `vite.config.ts`:
```typescript
server: {
  host: '0.0.0.0',
  port: 8011,
}
```

Then just `npm run dev`.

## The Point

By using the EXACT same stack every time, the agent:
1. Never wastes tokens deciding between libraries
2. Produces consistent, professional output
3. Can reuse patterns from training data (shadcn is extremely well-documented)
4. Generates accessible components by default
5. Creates output that looks modern without explicit design instructions
