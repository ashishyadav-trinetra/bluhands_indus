---
name: design-system
type: knowledge
version: 2.0.0
agent: CodeActAgent
triggers:
- website
- landing page
- frontend
- UI
- component
- page
- layout
- design
- styled
- responsive
- hero
- dashboard
- card
- button
- form
- modal
- sidebar
- navbar
- footer
- header
- section
- build
- create
- make
- app
- site
---

# MANDATORY DESIGN RULES — READ BEFORE WRITING ANY CODE

## YOU MUST DO THESE THINGS. NO EXCEPTIONS.

### 1. EVERY section gets this wrapper:
```tsx
<section className="py-16 md:py-20">
  <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    {/* content here */}
  </div>
</section>
```
NEVER put content without `max-w-7xl mx-auto px-4 sm:px-6 lg:px-8`.

### 2. Navbar MUST be:
```tsx
<header className="sticky top-0 z-50 bg-white border-b border-gray-100">
  <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between h-16">
    <div className="flex items-center gap-8">
      <span className="text-xl font-bold">Brand</span>
      <nav className="hidden md:flex items-center gap-6 text-sm font-medium text-gray-600">
        <a className="hover:text-gray-900">Link</a>
      </nav>
    </div>
    <button className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700">
      CTA
    </button>
  </div>
</header>
```

### 3. Hero MUST be:
```tsx
<section className="py-20 md:py-28">
  <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
    <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold tracking-tight text-gray-900 max-w-4xl mx-auto">
      Headline
    </h1>
    <p className="mt-6 text-lg md:text-xl text-gray-600 max-w-2xl mx-auto">
      Subtext
    </p>
    <div className="mt-10 flex items-center justify-center gap-4">
      <button className="bg-blue-600 text-white px-6 py-3 rounded-lg text-sm font-medium hover:bg-blue-700">
        Primary CTA
      </button>
      <button className="border border-gray-300 text-gray-700 px-6 py-3 rounded-lg text-sm font-medium hover:bg-gray-50">
        Secondary CTA
      </button>
    </div>
  </div>
</section>
```
ALWAYS add `max-w-4xl mx-auto` on h1 and `max-w-2xl mx-auto` on the description.

### 4. Feature grid MUST be:
```tsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
  <div className="bg-white rounded-xl border border-gray-200 p-6 hover:shadow-md transition-shadow">
    <div className="w-12 h-12 bg-blue-50 rounded-lg flex items-center justify-center mb-4">
      <Icon className="w-6 h-6 text-blue-600" />
    </div>
    <h3 className="text-lg font-semibold text-gray-900 mb-2">Title</h3>
    <p className="text-sm text-gray-600 leading-relaxed">Description</p>
  </div>
</div>
```
ALWAYS use `border border-gray-200 rounded-xl p-6` on cards. NEVER leave cards without borders.

### 5. Section headings MUST be:
```tsx
<div className="text-center mb-12">
  <p className="text-sm font-semibold text-blue-600 uppercase tracking-wide mb-3">Section Label</p>
  <h2 className="text-3xl md:text-4xl font-bold text-gray-900 tracking-tight">Section Title</h2>
  <p className="mt-4 text-lg text-gray-600 max-w-2xl mx-auto">Description</p>
</div>
```

### 6. Footer MUST be:
```tsx
<footer className="bg-gray-900 text-gray-400 py-12">
  <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    ...
  </div>
</footer>
```

### 7. Stats row:
```tsx
<div className="grid grid-cols-2 md:grid-cols-4 gap-8 py-12 border-y border-gray-200">
  <div className="text-center">
    <div className="text-3xl md:text-4xl font-bold text-gray-900">100+</div>
    <div className="text-sm text-gray-600 mt-1">Label</div>
  </div>
</div>
```

### 8. Testimonial card:
```tsx
<div className="bg-white rounded-xl border border-gray-200 p-6">
  <div className="flex gap-1 mb-4">
    {[...Array(5)].map((_, i) => <Star key={i} className="w-4 h-4 fill-yellow-400 text-yellow-400" />)}
  </div>
  <p className="text-gray-600 text-sm leading-relaxed mb-4">"Quote text"</p>
  <div className="flex items-center gap-3">
    <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center text-sm font-medium text-blue-700">AB</div>
    <div>
      <div className="text-sm font-medium text-gray-900">Name</div>
      <div className="text-xs text-gray-500">Title</div>
    </div>
  </div>
</div>
```

## RULES THAT MUST NEVER BE BROKEN:

1. **EVERY section** gets `max-w-7xl mx-auto px-4 sm:px-6 lg:px-8`. NO EXCEPTIONS.
2. **Heading text** NEVER exceeds `max-w-4xl mx-auto`. Descriptions `max-w-2xl mx-auto`.
3. **Cards** ALWAYS have `border border-gray-200 rounded-xl p-6`.
4. **Body text** is ALWAYS `text-gray-600`, NEVER `text-black` or `text-white` on light bg.
5. **Only ONE primary button** (solid color) per section. Others are outline.
6. **Spacing** between sections is `py-16 md:py-20`. Hero is `py-20 md:py-28`.
7. **Font sizes**: h1=`text-4xl md:text-5xl`, h2=`text-3xl md:text-4xl`, h3=`text-lg`, body=`text-sm` or `text-base`.
8. **Grid gaps**: `gap-8` for cards, `gap-6` for tight grids, `gap-4` for buttons.
9. **Colors**: Primary=`blue-600`, Text=`gray-900`, Body=`gray-600`, Subtle=`gray-400`, BG=`gray-50`.
10. **Rounded corners**: `rounded-xl` for cards, `rounded-lg` for buttons/inputs, `rounded-full` for avatars.

## SERVER CONFIG:
- Port: 8011
- Host: 0.0.0.0
- Vite: Add to vite.config.ts `server: { host: '0.0.0.0', port: 8011 }`
- Express: `app.listen(8011, '0.0.0.0')`

## INSTALL COMMANDS:
```bash
npm create vite@latest . -- --template react-ts
npm install
npm install -D tailwindcss @tailwindcss/vite
npm install lucide-react
```

Add to `vite.config.ts`:
```typescript
import tailwindcss from '@tailwindcss/vite'
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { host: '0.0.0.0', port: 8011 }
})
```

Add to `src/index.css`:
```css
@import "tailwindcss";
```

Add Google Font to `index.html`:
```html
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
```
