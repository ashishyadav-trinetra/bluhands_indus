"use client";

import { useState } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getApi } from "@/lib/api";
import { useOnboarding } from "@/lib/state";
import { StepShell } from "./StepShell";

const CATEGORIES = ["Apparel", "Thrift / Vintage", "Electronics", "Home & Living", "Beauty", "Other"];
const COUNTRIES = [
  { code: "IN", name: "India", currency: "INR" },
  { code: "US", name: "United States", currency: "USD" },
  { code: "GB", name: "United Kingdom", currency: "GBP" },
  { code: "AE", name: "United Arab Emirates", currency: "AED" },
];

export function BusinessStep() {
  const { state, dispatch } = useOnboarding();
  const { business } = state.data;
  const [busy, setBusy] = useState(false);

  const set = (patch: Partial<typeof business>) =>
    dispatch({ type: "update", patch: { business: patch } });

  const valid = business.storeName.trim() !== "";

  const onNext = async () => {
    setBusy(true);
    try {
      const orgId = state.orgId ?? "current";
      const { tenantId } = await getApi().createTenant(
        { industry: state.data.industry, business },
        orgId,
      );
      dispatch({ type: "setTenant", tenantId });
      dispatch({ type: "next" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <StepShell
      title="Tell us about your store"
      description="The basics we need to set up your storefront and currency."
      onNext={onNext}
      nextLabel={busy ? "Saving…" : "Continue"}
      nextDisabled={!valid || busy}
    >
      <div>
        <Label htmlFor="storeName">Store name</Label>
        <Input
          id="storeName"
          value={business.storeName}
          onChange={(e) => set({ storeName: e.target.value })}
          placeholder="MirrorFit Retail"
        />
      </div>
      <div>
        <Label htmlFor="category">Category</Label>
        <select
          id="category"
          className="h-10 w-full rounded-md border border-border bg-card px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          value={business.category}
          onChange={(e) => set({ category: e.target.value })}
        >
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>
      <div>
        <Label htmlFor="country">Country</Label>
        <select
          id="country"
          className="h-10 w-full rounded-md border border-border bg-card px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          value={business.country}
          onChange={(e) => {
            const c = COUNTRIES.find((x) => x.code === e.target.value);
            set({ country: e.target.value, currency: c?.currency ?? business.currency });
          }}
        >
          {COUNTRIES.map((c) => (
            <option key={c.code} value={c.code}>
              {c.name} ({c.currency})
            </option>
          ))}
        </select>
        <p className="mt-1 text-xs text-muted-foreground">
          Your store currency will be {business.currency}.
        </p>
      </div>
      <div>
        <Label htmlFor="support">Support email</Label>
        <Input
          id="support"
          type="email"
          value={business.supportEmail}
          onChange={(e) => set({ supportEmail: e.target.value })}
          placeholder="support@yourstore.com"
        />
      </div>
    </StepShell>
  );
}
