---
name: animation-interaction
type: knowledge
version: 1.0.0
agent: CodeActAgent
triggers:
- animation
- animate
- transition
- motion
- scroll
- hover effect
- loading
- skeleton
- spinner
- fade
- slide
- interactive
- smooth
---

# Animation & Interaction — Motion Design Rules

## Install Framer Motion

```bash
npm install framer-motion
```

## Rule: Subtlety Over Flash

- Animations should be FAST (200-400ms)
- Only animate on ENTRY, not on every re-render
- Use `ease-out` for entrances, `ease-in` for exits
- Never animate more than 3 properties simultaneously
- No bouncing, no excessive spring physics

## Scroll-Triggered Animations

### Fade Up on Scroll (Most Common)

```tsx
import { motion } from 'framer-motion';

// Wrap any section that should animate on scroll
function FadeUp({ children, delay = 0 }: { children: React.ReactNode; delay?: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-50px' }}
      transition={{ duration: 0.5, delay, ease: 'easeOut' }}
    >
      {children}
    </motion.div>
  );
}

// Usage:
<FadeUp>
  <h2 className="text-3xl font-semibold">Features</h2>
</FadeUp>

// Staggered cards:
{features.map((f, i) => (
  <FadeUp key={f.title} delay={i * 0.1}>
    <Card>...</Card>
  </FadeUp>
))}
```

### Stagger Container

```tsx
const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

<motion.div
  variants={containerVariants}
  initial="hidden"
  whileInView="visible"
  viewport={{ once: true }}
  className="grid grid-cols-1 md:grid-cols-3 gap-6"
>
  {items.map((item) => (
    <motion.div key={item.id} variants={itemVariants}>
      <Card>...</Card>
    </motion.div>
  ))}
</motion.div>
```

## Page Transitions

```tsx
// src/components/PageTransition.tsx
import { motion } from 'framer-motion';

export function PageTransition({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.3 }}
    >
      {children}
    </motion.div>
  );
}

// Wrap each page component:
export function AboutPage() {
  return (
    <PageTransition>
      <section>...</section>
    </PageTransition>
  );
}
```

## Hover Effects (CSS-Only, No Framer Needed)

```tsx
// Card hover — lift + shadow
<Card className="transition-all duration-200 hover:shadow-lg hover:-translate-y-1">

// Button hover — already built into shadcn
<Button>Click Me</Button>  // Has hover states built in

// Link hover — underline animation
<a className="relative inline-block after:absolute after:bottom-0 after:left-0 after:h-px after:w-0 after:bg-primary after:transition-all hover:after:w-full">
  Learn More
</a>

// Image hover — scale
<div className="overflow-hidden rounded-lg">
  <img className="transition-transform duration-300 hover:scale-105" src="..." />
</div>
```

## Loading States

### Skeleton Loaders

```bash
npx shadcn@latest add skeleton
```

```tsx
import { Skeleton } from '@/components/ui/skeleton';

// Card skeleton
function CardSkeleton() {
  return (
    <div className="p-6 border rounded-lg space-y-3">
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-4 w-1/2" />
      <Skeleton className="h-20 w-full" />
    </div>
  );
}

// Page skeleton
function PageSkeleton() {
  return (
    <div className="max-w-6xl mx-auto px-4 md:px-6 py-20 space-y-8">
      <Skeleton className="h-12 w-1/2 mx-auto" />
      <Skeleton className="h-6 w-2/3 mx-auto" />
      <div className="grid grid-cols-3 gap-6 mt-12">
        <CardSkeleton />
        <CardSkeleton />
        <CardSkeleton />
      </div>
    </div>
  );
}
```

### Spinner

```tsx
import { Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

<Button disabled>
  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
  Loading...
</Button>
```

## Counter / Number Animation

```tsx
import { useEffect, useState } from 'react';
import { motion, useInView } from 'framer-motion';

function AnimatedNumber({ value, duration = 2 }: { value: number; duration?: number }) {
  const [count, setCount] = useState(0);
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true });

  useEffect(() => {
    if (!isInView) return;
    let start = 0;
    const end = value;
    const stepTime = (duration * 1000) / end;
    const timer = setInterval(() => {
      start += 1;
      setCount(start);
      if (start >= end) clearInterval(timer);
    }, stepTime);
    return () => clearInterval(timer);
  }, [isInView, value, duration]);

  return <span ref={ref}>{count}</span>;
}

// Usage: <AnimatedNumber value={150} />+
```

## When to Animate (Decision Tree)

```
Is the element entering the viewport for the first time?
├── Yes → FadeUp animation (opacity + translateY)
└── No → Don't animate

Is the user hovering a card/button?
├── Card → CSS shadow + translateY (-1px)
├── Button → Already handled by shadcn
└── Image → CSS scale(1.05) with overflow-hidden

Is data loading?
├── Initial page load → Skeleton loader
├── Button action → Spinner inside button
└── Form submit → Disable + spinner

Is the user navigating between pages?
├── Yes → PageTransition (opacity fade, 300ms)
└── No → Don't animate
```

## Anti-Patterns

- ❌ Animating on EVERY re-render (use `viewport={{ once: true }}`)
- ❌ Bounce/spring animations on business sites (too playful)
- ❌ Animations longer than 500ms (feels sluggish)
- ❌ Animating layout properties (width, height) — use opacity and transform only
- ❌ Custom CSS `@keyframes` when Framer Motion or Tailwind `animate-*` exists
- ❌ Multiple competing animations on screen simultaneously
