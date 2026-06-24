import { Filters } from "@/components/filters";
import { ProductGrid } from "@/components/product-grid";
import { getProducts } from "@/lib/medusa";
import type { Product } from "@/lib/types";

// Server component: fetches products from the tenant's Medusa backend.
export default async function HomePage() {
  let products: Product[] = [];
  let error: string | null = null;
  try {
    products = await getProducts();
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load products";
  }

  return (
    <main className="container py-8">
      <header className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Storefront</h1>
      </header>

      <div className="mb-6">
        <Filters />
      </div>

      {error ? (
        <p className="rounded-md border border-border bg-muted p-4 text-muted-foreground">
          Could not load products ({error}). Check the Medusa connection.
        </p>
      ) : (
        <ProductGrid products={products} />
      )}
    </main>
  );
}
