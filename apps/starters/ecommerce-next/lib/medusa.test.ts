import { describe, expect, it } from "vitest";

import { mapProduct, type RawMedusaProduct } from "./medusa";

describe("mapProduct", () => {
  it("normalizes a full raw product", () => {
    const raw: RawMedusaProduct = {
      id: "prod_1",
      title: "Vintage Jacket",
      description: "Lovely",
      thumbnail: "https://img/x.png",
      variants: [{ prices: [{ amount: 250000, currency_code: "inr" }] }],
    };
    const p = mapProduct(raw);
    expect(p).toEqual({
      id: "prod_1",
      title: "Vintage Jacket",
      description: "Lovely",
      thumbnail: "https://img/x.png",
      priceMinor: 250000,
      currency: "INR",
    });
  });

  it("applies safe defaults for missing fields", () => {
    const p = mapProduct({ id: "prod_2" });
    expect(p.title).toBe("Untitled");
    expect(p.description).toBe("");
    expect(p.thumbnail).toBeNull();
    expect(p.priceMinor).toBe(0);
    expect(p.currency).toBe("INR");
  });
});
