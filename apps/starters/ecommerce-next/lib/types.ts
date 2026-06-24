/** Normalized product shape the UI renders (decoupled from Medusa's raw schema). */
export interface Product {
  id: string;
  title: string;
  description: string;
  thumbnail: string | null;
  priceMinor: number; // smallest currency unit
  currency: string;
}

export interface ProductFilters {
  q?: string;
  minPriceMinor?: number;
  maxPriceMinor?: number;
  collectionId?: string;
}
