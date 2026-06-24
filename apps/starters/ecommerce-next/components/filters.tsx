"use client";

import { Button } from "@/components/ui/button";

/**
 * Filter bar placeholder. The agent wires these to the Medusa query params
 * declared in the capability manifest (price/size/color/collection) during a
 * build, and its Playwright self-test exercises each one.
 */
export function Filters() {
  return (
    <div className="flex flex-wrap gap-2" aria-label="Product filters">
      <Button variant="outline" size="sm">Price</Button>
      <Button variant="outline" size="sm">Size</Button>
      <Button variant="outline" size="sm">Color</Button>
      <Button variant="outline" size="sm">In stock</Button>
    </div>
  );
}
