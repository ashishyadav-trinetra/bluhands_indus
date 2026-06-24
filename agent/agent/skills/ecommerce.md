# E-commerce storefront — required pages and patterns

## Pages to build

| Route | Purpose |
|---|---|
| `/` | Home — hero, featured products, category links |
| `/products` | Catalog — all products, filter by category, sort |
| `/products/[handle]` | Product detail page (PDP) |
| `/cart` | Cart page (fallback if no drawer) |
| `/checkout` | Checkout form + payment |

## Site-wide header

```tsx
// Sticky, blurred, with item count badge on cart icon
<header className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
  <div className="container mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
    {/* Logo / store name */}
    <Link href="/" className="text-xl font-bold tracking-tight">{storeName}</Link>

    {/* Desktop category nav */}
    <nav className="hidden items-center gap-6 md:flex">
      {categories.map((cat) => (
        <Link key={cat.id} href={`/products?category=${cat.handle}`}
          className="text-sm font-medium transition-colors hover:text-primary">
          {cat.name}
        </Link>
      ))}
    </nav>

    {/* Cart icon + count + mobile hamburger */}
    <div className="flex items-center gap-3">
      <button onClick={openCart} className="relative">
        <ShoppingBagIcon className="h-6 w-6" />
        {itemCount > 0 && (
          <Badge className="absolute -right-2 -top-2 h-5 w-5 rounded-full p-0 text-xs">{itemCount}</Badge>
        )}
      </button>
      {/* Mobile menu trigger → Sheet */}
    </div>
  </div>
</header>
```

## Home page

```
1. Hero — full-width banner with brand tagline and a CTA button
2. Featured products — horizontal scroll on mobile, 4-column grid on desktop
3. Category links — card grid (image + name), max 6 categories
4. Footer — store name, copyright
```

## Catalog page (`/products`)

```
1. Category filter bar — horizontal scrollable pills (All, Women, Men, etc.)
2. Sort dropdown — "Newest", "Price: Low → High", "Price: High → Low"
3. Product grid — responsive, with Skeleton while loading
4. Pagination or "Load more" button
```

## Product detail page (PDP)

```
1. Breadcrumb — Home > Category > Product
2. Images — main image + thumbnail strip (or simple next/prev arrows)
3. Product info: name, price (with original price if on sale), description
4. Variant selector (size/color) — Radio or Select, required before add-to-cart
5. Add to cart button — shows spinner while adding, then opens cart drawer
6. Stock indicator — "Only N left" if inventory < 5, "Out of stock" if 0
```

## Cart drawer (right Sheet, slides over page)

```tsx
// Always open on the same page — never navigate to /cart to view the cart
// The /cart route is only for users who go there directly

<Sheet open={open} onOpenChange={setOpen}>
  <SheetContent side="right" className="flex w-full flex-col sm:max-w-lg">
    <SheetHeader><SheetTitle>Your Cart ({count})</SheetTitle></SheetHeader>
    <div className="flex-1 overflow-y-auto divide-y">
      {cart.items.map((item) => (
        <div key={item.id} className="flex gap-4 py-4">
          <Image src={item.thumbnail} width={64} height={64} className="rounded object-cover" />
          <div className="flex flex-1 flex-col">
            <span className="font-medium text-sm">{item.title}</span>
            <span className="text-muted-foreground text-xs">{item.variant.title}</span>
            <div className="mt-auto flex items-center justify-between">
              <QuantityControl quantity={item.quantity} onChange={(q) => updateItem(item.id, q)} />
              <span className="font-semibold">{formatPrice(item.unit_price * item.quantity)}</span>
            </div>
          </div>
          <button onClick={() => removeItem(item.id)}><XIcon className="h-4 w-4" /></button>
        </div>
      ))}
    </div>
    <div className="border-t space-y-3 pt-4">
      <div className="flex justify-between font-semibold">
        <span>Subtotal</span><span>{formatPrice(subtotal)}</span>
      </div>
      <p className="text-xs text-muted-foreground">Shipping and taxes calculated at checkout.</p>
      <Button asChild className="w-full" size="lg">
        <Link href="/checkout">Checkout</Link>
      </Button>
    </div>
  </SheetContent>
</Sheet>
```

## Checkout page

```
1. Shipping address form (name, email, address, city, postal code, country)
2. Payment section — render Medusa's payment UI component or a card form
3. Order summary sidebar (items, subtotal, shipping, total)
4. "Place order" button → POST /store/carts/<id>/complete
```

## Performance rules

- All product images through `next/image` with explicit `width`, `height`, and `sizes`
- Use `loading="lazy"` on all images not in the above-the-fold viewport
- Wrap every async data section in `<Suspense fallback={<Skeleton />}>`
- Never use `export default async function Page()` at the top level without a Suspense boundary wrapping the async child
