import { ShoppingCart } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter } from "@/components/ui/card";
import type { Product } from "@/lib/types";
import { formatPrice } from "@/lib/utils";

/** A single product tile. The agent restyles via tokens, not by rewriting this. */
export function ProductCard({ product }: { product: Product }) {
  return (
    <Card className="overflow-hidden">
      <CardContent className="p-0">
        <div className="aspect-square w-full bg-muted">
          {product.thumbnail ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={product.thumbnail} alt={product.title} className="h-full w-full object-cover" />
          ) : (
            <div className="flex h-full items-center justify-center text-muted-foreground">No image</div>
          )}
        </div>
        <div className="p-4">
          <h3 className="line-clamp-1 font-medium">{product.title}</h3>
          <p className="mt-1 font-semibold">{formatPrice(product.priceMinor, product.currency)}</p>
        </div>
      </CardContent>
      <CardFooter>
        <Button className="w-full" size="sm">
          <ShoppingCart className="h-4 w-4" /> Add to cart
        </Button>
      </CardFooter>
    </Card>
  );
}
