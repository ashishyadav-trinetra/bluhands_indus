---
name: multi-page-router
type: knowledge
version: 1.0.0
agent: CodeActAgent
triggers:
- multi-page
- multiple pages
- router
- routing
- navigation
- pages
- about page
- contact page
- pricing page
- blog page
- sign in page
- sign up page
- dashboard page
---

# Multi-Page Router — React Router Setup

When the project needs multiple pages, set up React Router with consistent layouts.

## Install

```bash
npm install react-router-dom
```

## Router Structure

```tsx
// src/App.tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/layout/Layout';
import { HomePage } from './pages/HomePage';
import { AboutPage } from './pages/AboutPage';
import { PricingPage } from './pages/PricingPage';
import { ContactPage } from './pages/ContactPage';
import { NotFoundPage } from './pages/NotFoundPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<HomePage />} />
          <Route path="about" element={<AboutPage />} />
          <Route path="pricing" element={<PricingPage />} />
          <Route path="contact" element={<ContactPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
```

## Shared Layout

```tsx
// src/components/layout/Layout.tsx
import { Outlet } from 'react-router-dom';
import { Navbar } from './Navbar';
import { Footer } from './Footer';

export function Layout() {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Navbar />
      <main className="flex-1">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}
```

## Navbar with Active Links

```tsx
// src/components/layout/Navbar.tsx
import { Link, useLocation } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

const navLinks = [
  { path: '/', label: 'Home' },
  { path: '/about', label: 'About' },
  { path: '/pricing', label: 'Pricing' },
  { path: '/contact', label: 'Contact' },
];

export function Navbar() {
  const { pathname } = useLocation();

  return (
    <header className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="max-w-6xl mx-auto px-4 md:px-6 flex h-16 items-center justify-between">
        <div className="flex items-center gap-8">
          <Link to="/" className="text-lg font-bold">
            Brand
          </Link>
          <nav className="hidden md:flex items-center gap-6">
            {navLinks.map((link) => (
              <Link
                key={link.path}
                to={link.path}
                className={cn(
                  'text-sm transition-colors',
                  pathname === link.path
                    ? 'text-foreground font-medium'
                    : 'text-muted-foreground hover:text-foreground'
                )}
              >
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm">Sign In</Button>
          <Button size="sm">Get Started</Button>
        </div>
      </div>
    </header>
  );
}
```

## Page Template

Every page follows this structure:

```tsx
// src/pages/AboutPage.tsx
export function AboutPage() {
  return (
    <>
      {/* Hero / Page Header */}
      <section className="py-20 md:py-28">
        <div className="max-w-6xl mx-auto px-4 md:px-6 text-center">
          <h1 className="text-4xl md:text-5xl font-bold tracking-tight mb-4">
            About Us
          </h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Page description goes here.
          </p>
        </div>
      </section>

      {/* Content Sections */}
      <section className="py-16">
        <div className="max-w-6xl mx-auto px-4 md:px-6">
          {/* Section content */}
        </div>
      </section>
    </>
  );
}
```

## File Structure

```
src/
├── components/
│   ├── layout/
│   │   ├── Layout.tsx       # Shared layout (navbar + footer + outlet)
│   │   ├── Navbar.tsx       # Navigation with active states
│   │   ├── Footer.tsx       # Site footer
│   │   └── MobileNav.tsx    # Mobile hamburger menu (Sheet)
│   ├── sections/            # Reusable page sections
│   │   ├── Hero.tsx
│   │   ├── Features.tsx
│   │   ├── Pricing.tsx
│   │   ├── Testimonials.tsx
│   │   └── CTA.tsx
│   └── ui/                  # shadcn components
├── pages/
│   ├── HomePage.tsx
│   ├── AboutPage.tsx
│   ├── PricingPage.tsx
│   ├── ContactPage.tsx
│   ├── BlogPage.tsx
│   ├── SignInPage.tsx
│   └── NotFoundPage.tsx
├── App.tsx                  # Router setup
└── main.tsx                 # Entry point
```

## Mobile Navigation (Hamburger Menu)

```bash
npx shadcn@latest add sheet
```

```tsx
// src/components/layout/MobileNav.tsx
import { Menu } from 'lucide-react';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { Link } from 'react-router-dom';

export function MobileNav() {
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="ghost" size="icon" className="md:hidden">
          <Menu className="h-5 w-5" />
        </Button>
      </SheetTrigger>
      <SheetContent side="left">
        <nav className="flex flex-col gap-4 mt-8">
          <Link to="/" className="text-lg font-medium">Home</Link>
          <Link to="/about" className="text-lg font-medium">About</Link>
          <Link to="/pricing" className="text-lg font-medium">Pricing</Link>
          <Link to="/contact" className="text-lg font-medium">Contact</Link>
        </nav>
      </SheetContent>
    </Sheet>
  );
}
```

## Scroll to Top on Navigation

```tsx
// src/components/ScrollToTop.tsx
import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

export function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  return null;
}

// Add to App.tsx inside BrowserRouter:
<ScrollToTop />
```

## 404 Not Found Page

```tsx
// src/pages/NotFoundPage.tsx
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';

export function NotFoundPage() {
  return (
    <section className="py-28">
      <div className="max-w-6xl mx-auto px-4 md:px-6 text-center">
        <h1 className="text-6xl font-bold tracking-tight mb-4">404</h1>
        <p className="text-lg text-muted-foreground mb-8">Page not found</p>
        <Button asChild>
          <Link to="/">Go Home</Link>
        </Button>
      </div>
    </section>
  );
}
```
