# Medusa Store API integration

## Client (already configured in the starter)

```ts
// lib/medusa.ts is already present — import from there
import { sdk } from "@/lib/medusa"
```

## Key endpoints

```
Products
  GET  /store/products                          list all products (paginated)
  GET  /store/products?category_id[]=<id>       filter by category
  GET  /store/products/<id>                     single product + variants
  GET  /store/product-categories                list categories

Cart
  POST   /store/carts                            create cart  → { cart: { id } }
  GET    /store/carts/<id>                       retrieve cart
  POST   /store/carts/<id>/line-items            add item     → { cart }
  POST   /store/carts/<id>/line-items/<lid>      update qty   → { cart }
  DELETE /store/carts/<id>/line-items/<lid>      remove item  → { cart }

Checkout
  POST /store/carts/<id>/payment-sessions        init payment
  POST /store/carts/<id>/complete                complete order
```

## React Query patterns — use these, never raw `useEffect` for data fetching

```tsx
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { sdk } from "@/lib/medusa"

// List products
const { data, isLoading } = useQuery({
  queryKey: ["products", categoryId, page],
  queryFn: () =>
    sdk.store.product.list({ limit: 12, offset: page * 12, category_id: categoryId ? [categoryId] : undefined }),
})

// Single product
const { data: product } = useQuery({
  queryKey: ["product", handle],
  queryFn: () => sdk.store.product.retrieve(handle),
})

// Categories
const { data: categories } = useQuery({
  queryKey: ["categories"],
  queryFn: () => sdk.store.productCategory.list({ limit: 50 }),
  staleTime: 5 * 60 * 1000,
})
```

## Cart management

Store the cart ID in localStorage (the starter may already do this):

```tsx
// Create or restore cart
async function getOrCreateCart(): Promise<string> {
  const stored = localStorage.getItem("cartId")
  if (stored) {
    try {
      await sdk.store.cart.retrieve(stored)
      return stored
    } catch {}
  }
  const { cart } = await sdk.store.cart.create({})
  localStorage.setItem("cartId", cart.id)
  return cart.id
}

// Add to cart mutation
const addToCart = useMutation({
  mutationFn: async ({ variantId, quantity }: { variantId: string; quantity: number }) => {
    const cartId = await getOrCreateCart()
    return sdk.store.cart.createLineItem(cartId, { variant_id: variantId, quantity })
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ["cart"] })
    openCartDrawer()
  },
})
```

## Pricing

Medusa prices are integers (smallest currency unit — cents for USD, paise for INR):

```tsx
export function formatPrice(amount: number, currencyCode = "usd"): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currencyCode.toUpperCase(),
  }).format(amount / 100)
}

// Usage: formatPrice(variant.prices[0].amount, variant.prices[0].currency_code)
```

## Variant selection

Products have variants (size, color, etc.). Always render a variant selector on the PDP:

```tsx
// Get the selected variant's price
const selectedVariant = product.variants.find((v) => v.id === selectedVariantId)
const price = selectedVariant?.prices[0]

// Disable add-to-cart until a variant is chosen
<Button disabled={!selectedVariantId || !selectedVariant?.inventory_quantity}>
  {selectedVariant?.inventory_quantity === 0 ? "Out of stock" : "Add to cart"}
</Button>
```
