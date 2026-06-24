"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SelectableCard } from "@/components/ui/card";
import { useOnboarding } from "@/lib/state";
import { StepShell } from "./StepShell";

const VIBES = [
  { id: "minimal", label: "Minimal", hint: "Clean, lots of whitespace" },
  { id: "playful", label: "Playful", hint: "Bold colors, friendly" },
  { id: "premium", label: "Premium", hint: "Dark, elegant, refined" },
];

export function BrandStep() {
  const { state, dispatch } = useOnboarding();
  const { brand } = state.data;

  const set = (patch: Partial<typeof brand>) =>
    dispatch({ type: "update", patch: { brand: patch } });

  return (
    <StepShell
      title="Your brand"
      description="This sets the look of your store. You can fine-tune it later."
    >
      <div>
        <Label htmlFor="tagline">Tagline</Label>
        <Input
          id="tagline"
          value={brand.tagline}
          onChange={(e) => set({ tagline: e.target.value })}
          placeholder="Curated vintage, delivered."
        />
      </div>

      <div>
        <Label>Logo</Label>
        <label className="flex h-24 cursor-pointer items-center justify-center rounded-md border border-dashed border-border bg-muted/40 text-sm text-muted-foreground hover:bg-muted">
          {brand.logoName ? `Selected: ${brand.logoName}` : "Click to upload a logo (optional)"}
          <input
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => set({ logoName: e.target.files?.[0]?.name ?? null })}
          />
        </label>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label htmlFor="primary">Primary color</Label>
          <div className="flex items-center gap-2">
            <input
              id="primary"
              type="color"
              value={brand.primaryColor}
              onChange={(e) => set({ primaryColor: e.target.value })}
              className="h-10 w-12 cursor-pointer rounded-md border border-border bg-card"
            />
            <Input value={brand.primaryColor} onChange={(e) => set({ primaryColor: e.target.value })} />
          </div>
        </div>
        <div>
          <Label htmlFor="accent">Accent color</Label>
          <div className="flex items-center gap-2">
            <input
              id="accent"
              type="color"
              value={brand.accentColor}
              onChange={(e) => set({ accentColor: e.target.value })}
              className="h-10 w-12 cursor-pointer rounded-md border border-border bg-card"
            />
            <Input value={brand.accentColor} onChange={(e) => set({ accentColor: e.target.value })} />
          </div>
        </div>
      </div>

      <div>
        <Label>Vibe</Label>
        <div className="grid grid-cols-3 gap-3">
          {VIBES.map((v) => (
            <SelectableCard
              key={v.id}
              selected={brand.vibe === v.id}
              onClick={() => set({ vibe: v.id })}
            >
              <p className="text-sm font-medium">{v.label}</p>
              <p className="mt-1 text-xs text-muted-foreground">{v.hint}</p>
            </SelectableCard>
          ))}
        </div>
      </div>
    </StepShell>
  );
}
