"use client";

import { useRef } from "react";
import { ImagePlus, Plus, Trash2, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useOnboarding } from "@/lib/state";
import type { Product } from "@/lib/types";
import { StepShell } from "./StepShell";

const TEMPLATE_CSV = "name,price,stock\nSample product,19.99,100\n";

function newProduct(): Product {
  return { id: `p_${Math.random().toString(36).slice(2, 9)}`, name: "", price: "", stock: "", images: [] };
}

export function CatalogStep() {
  const { state, dispatch } = useOnboarding();
  const { products } = state.data.catalog;
  const importInputRef = useRef<HTMLInputElement>(null);

  const setProducts = (next: Product[]) =>
    dispatch({ type: "update", patch: { catalog: { products: next } } });

  const updateProduct = (id: string, patch: Partial<Product>) =>
    setProducts(products.map((p) => (p.id === id ? { ...p, ...patch } : p)));

  const removeProduct = (id: string) => setProducts(products.filter((p) => p.id !== id));

  const addProduct = () => setProducts([...products, newProduct()]);

  const addImages = (id: string, files: FileList | null) => {
    if (!files || files.length === 0) return;
    const names = Array.from(files).map((f) => f.name);
    const current = products.find((p) => p.id === id);
    updateProduct(id, { images: [...(current?.images ?? []), ...names] });
  };

  const onImportFile = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    // Stub: real CSV/Excel parsing happens server-side (T-A07). We just
    // record that an import file was chosen.
    dispatch({ type: "update", patch: { catalog: { choice: "import" } } });
  };

  const downloadTemplate = () => {
    const blob = new Blob([TEMPLATE_CSV], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "product-template.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  const valid = products.some((p) => p.name.trim() !== "");

  return (
    <StepShell
      title="Add your products"
      description="Add manually with images, or bulk-import a CSV/Excel file."
      nextDisabled={!valid}
    >
      <Card className="flex flex-wrap items-center justify-between gap-4 border-dashed p-4">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 flex-none items-center justify-center rounded-md bg-muted">
            <Upload className="h-4 w-4" />
          </span>
          <div>
            <p className="text-sm font-medium">Import products</p>
            <p className="text-xs text-muted-foreground">CSV, TSV or Excel — columns: name, price, stock</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <button type="button" onClick={downloadTemplate} className="text-sm text-primary hover:underline">
            Download template
          </button>
          <input
            ref={importInputRef}
            type="file"
            accept=".csv,.tsv,.xlsx,.xls"
            className="hidden"
            onChange={(e) => onImportFile(e.target.files)}
          />
          <Button size="sm" onClick={() => importInputRef.current?.click()}>
            <Upload className="h-4 w-4" />
            Upload file
          </Button>
        </div>
      </Card>

      <div className="mt-5 space-y-3">
        {products.map((product, i) => (
          <Card key={product.id} className="p-4">
            <div className="flex flex-wrap items-center gap-2">
              <Input
                value={product.name}
                onChange={(e) => updateProduct(product.id, { name: e.target.value })}
                placeholder={`Product ${i + 1} name`}
                className="min-w-[140px] flex-1"
              />
              <Input
                value={product.price}
                onChange={(e) => updateProduct(product.id, { price: e.target.value })}
                placeholder="Price"
                className="w-24 flex-none"
                inputMode="decimal"
              />
              <Input
                value={product.stock}
                onChange={(e) => updateProduct(product.id, { stock: e.target.value })}
                placeholder="Stock"
                className="w-20 flex-none"
                inputMode="numeric"
              />
              <Button
                variant="outline"
                size="icon"
                className="flex-none"
                onClick={() => removeProduct(product.id)}
                disabled={products.length === 1}
                aria-label="Remove product"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>

            <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-3">
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Product images
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {product.images.length === 0
                    ? "No images yet — upload one or more."
                    : product.images.join(", ")}
                </p>
              </div>
              <label>
                <input
                  type="file"
                  accept="image/*"
                  multiple
                  className="hidden"
                  onChange={(e) => addImages(product.id, e.target.files)}
                />
                <span className="inline-flex h-9 cursor-pointer items-center gap-2 rounded-md border border-border px-3 text-sm hover:bg-muted">
                  <ImagePlus className="h-4 w-4" />
                  Add images
                </span>
              </label>
            </div>
          </Card>
        ))}
      </div>

      <Button variant="outline" className="mt-3" onClick={addProduct}>
        <Plus className="h-4 w-4" />
        Add another product
      </Button>
    </StepShell>
  );
}
