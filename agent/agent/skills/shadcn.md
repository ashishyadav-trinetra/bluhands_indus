# shadcn/ui usage patterns

## Importing components

Import from the `@/components/ui/` directory that the starter already provides:

```tsx
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
```

## Theme tokens — always use CSS variables, never hardcode hex

```tsx
// Correct — composable and respects the brand kit
className="bg-primary text-primary-foreground"
className="bg-card text-card-foreground border border-border"
className="text-muted-foreground text-sm"
className="bg-accent text-accent-foreground"

// Wrong — bypasses the brand tokens
className="bg-[#3b82f6] text-white"
className="border-gray-200"
```

## Layout patterns

```tsx
// Page container with responsive padding
<main className="container mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">

// Responsive product grid
<div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">

// Product card
<Card className="overflow-hidden transition-shadow hover:shadow-md">
  <div className="aspect-square overflow-hidden bg-muted">
    <Image className="h-full w-full object-cover transition-transform hover:scale-105" />
  </div>
  <CardContent className="p-4">
    <h3 className="font-medium leading-tight">{product.title}</h3>
    <p className="mt-1 text-lg font-semibold">{formatPrice(variant.prices[0].amount)}</p>
  </CardContent>
</Card>

// Sticky header
<header className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur">
  <div className="container mx-auto flex h-16 max-w-7xl items-center justify-between px-4">
```

## Typography scale

```tsx
<h1 className="text-3xl font-bold tracking-tight sm:text-4xl lg:text-5xl">
<h2 className="text-2xl font-semibold tracking-tight">
<h3 className="font-medium leading-snug">
<p className="text-muted-foreground leading-relaxed">
<span className="text-sm text-muted-foreground">
```

## Loading skeletons — always provide one

```tsx
{isLoading ? (
  <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
    {Array.from({ length: 6 }).map((_, i) => (
      <div key={i} className="space-y-3">
        <Skeleton className="aspect-square w-full rounded-lg" />
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
      </div>
    ))}
  </div>
) : (
  <ProductGrid products={products} />
)}
```

## Cart drawer (use Sheet, not a separate page)

```tsx
<Sheet open={cartOpen} onOpenChange={setCartOpen}>
  <SheetContent side="right" className="flex w-full flex-col sm:max-w-lg">
    <SheetHeader>
      <SheetTitle>Cart ({totalItems})</SheetTitle>
    </SheetHeader>
    <div className="flex-1 overflow-y-auto py-4">
      {/* line items */}
    </div>
    <div className="border-t pt-4">
      <div className="flex justify-between text-base font-medium">
        <span>Subtotal</span>
        <span>{formatPrice(subtotal)}</span>
      </div>
      <Button className="mt-4 w-full" size="lg">Proceed to Checkout</Button>
    </div>
  </SheetContent>
</Sheet>
```
