/**
 * Thin Medusa Store API client.
 *
 * The agent wires this to the tenant's Medusa backend via env vars (the values
 * come from the capability manifest + the control plane). `mapProduct` is a pure
 * function (unit-tested) that normalizes Medusa's raw product into our `Product`.
 */
import type { Product } from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_MEDUSA_URL ?? "http://localhost:9000";
const PUBLISHABLE_KEY = process.env.NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY ?? "";

/** Raw shape (subset) returned by Medusa's Store API for a product. */
export interface RawMedusaProduct {
  id: string;
  title?: string;
  description?: string | null;
  thumbnail?: string | null;
  variants?: Array<{
    prices?: Array<{ amount?: number; currency_code?: string }>;
  }>;
}

/** Pure: normalize a raw Medusa product into the UI `Product` (testable). */
export function mapProduct(raw: RawMedusaProduct): Product {
  const firstPrice = raw.variants?.[0]?.prices?.[0];
  return {
    id: raw.id,
    title: raw.title ?? "Untitled",
    description: raw.description ?? "",
    thumbnail: raw.thumbnail ?? null,
    priceMinor: firstPrice?.amount ?? 0,
    currency: (firstPrice?.currency_code ?? "INR").toUpperCase(),
  };
}

/** Fetch products from the Medusa Store API and normalize them. */
export async function getProducts(limit = 12): Promise<Product[]> {
  const res = await fetch(`${BASE_URL}/store/products?limit=${limit}`, {
    headers: PUBLISHABLE_KEY ? { "x-publishable-api-key": PUBLISHABLE_KEY } : {},
    // Storefront data can be cached briefly; the agent tunes this per page.
    next: { revalidate: 60 },
  });
  if (!res.ok) {
    throw new Error(`Medusa request failed: ${res.status}`);
  }
  const data = (await res.json()) as { products?: RawMedusaProduct[] };
  return (data.products ?? []).map(mapProduct);
}
