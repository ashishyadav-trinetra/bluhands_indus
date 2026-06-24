"use client";

import { useState } from "react";
import { CheckCircle2, Settings2, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SelectableCard } from "@/components/ui/card";
import { getApi } from "@/lib/api";
import { useOnboarding } from "@/lib/state";
import type { DnsRecord, DomainAvailability, DomainMode } from "@/lib/types";
import { StepShell } from "./StepShell";

const MODES: { id: DomainMode; label: string; hint: string }[] = [
  { id: "subdomain", label: "Use a free address", hint: "yourstore.bluhands.app — instant, change later" },
  { id: "byo", label: "I own a domain", hint: "Connect a domain you already have" },
  { id: "buy", label: "Buy a new domain", hint: "Search and register one now" },
];

const BYO_RECORDS = (domain: string): DnsRecord[] => [
  { type: "A", name: "@", value: "76.76.21.21" },
  { type: "CNAME", name: "www", value: "cname.bluhands.app" },
  { type: "TXT", name: "_bluhands", value: `verify=${domain}` },
];

// Load the Entri DNS-connect widget from their CDN (idempotent).
function loadEntriScript(): Promise<void> {
  if (typeof window !== "undefined" && (window as unknown as Record<string, unknown>).entri) {
    return Promise.resolve();
  }
  return new Promise((resolve, reject) => {
    const existing = document.querySelector('script[data-entri]');
    if (existing) { existing.addEventListener("load", () => resolve()); return; }
    const s = document.createElement("script");
    s.src = "https://cdn.entri.com/entri.js";
    s.setAttribute("data-entri", "1");
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("Failed to load Entri widget"));
    document.head.appendChild(s);
  });
}

export function DomainStep() {
  const { state, dispatch } = useOnboarding();
  const { domain } = state.data;
  const subBase = state.data.business.storeName
    ? state.data.business.storeName.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")
    : "your-store";

  const [query, setQuery] = useState("");
  const [checking, setChecking] = useState(false);
  const [result, setResult] = useState<DomainAvailability | null>(null);
  const [buying, setBuying] = useState(false);
  const [entriLoading, setEntriLoading] = useState(false);
  const [entriError, setEntriError] = useState<string | null>(null);
  const [dnsConfigured, setDnsConfigured] = useState(false);

  const setMode = (mode: DomainMode) => {
    setResult(null);
    if (mode === "subdomain") {
      dispatch({
        type: "update",
        patch: { domain: { mode, domain: `${subBase}.bluhands.app`, dnsRecords: [], purchased: false } },
      });
    } else {
      dispatch({ type: "update", patch: { domain: { mode, domain: "", dnsRecords: [], purchased: false } } });
    }
  };

  const connectByo = (value: string) =>
    dispatch({
      type: "update",
      patch: { domain: { mode: "byo", domain: value, dnsRecords: value ? BYO_RECORDS(value) : [], purchased: false } },
    });

  const check = async () => {
    setChecking(true);
    setResult(null);
    try {
      setResult(await getApi().checkDomain(query.trim()));
    } finally {
      setChecking(false);
    }
  };

  const buy = async () => {
    if (!result?.available) return;
    setBuying(true);
    try {
      await getApi().purchaseDomain(result.domain);
      dispatch({
        type: "update",
        patch: { domain: { mode: "buy", domain: result.domain, dnsRecords: [], purchased: true } },
      });
    } finally {
      setBuying(false);
    }
  };

  const connectWithEntri = async () => {
    if (!domain.domain.trim()) return;
    setEntriLoading(true);
    setEntriError(null);
    try {
      const session = await getApi().getDomainEntriSession(domain.domain.trim());
      await loadEntriScript();
      const entri = (window as unknown as Record<string, unknown>).entri as {
        showEntri: (config: {
          applicationId: string;
          token: string;
          dnsRecords: { type: string; host: string; value: string; ttl: number }[];
          onSuccess?: () => void;
          onError?: (err: unknown) => void;
        }) => void;
      } | undefined;
      if (!entri) throw new Error("Entri widget unavailable");
      entri.showEntri({
        applicationId: session.applicationId,
        token: session.token,
        dnsRecords: session.dnsRecords,
        onSuccess: () => setDnsConfigured(true),
        onError: () => setEntriError("DNS setup failed. You can configure the records manually below."),
      });
    } catch (e) {
      setEntriError(e instanceof Error ? e.message : "Could not open DNS setup widget.");
    } finally {
      setEntriLoading(false);
    }
  };

  const valid =
    (domain.mode === "subdomain" && domain.domain !== "") ||
    (domain.mode === "byo" && domain.domain.trim() !== "") ||
    (domain.mode === "buy" && domain.purchased);

  return (
    <StepShell
      title="Your web address"
      description="Where customers will find your store. You can change this later."
      nextDisabled={!valid}
    >
      <div className="space-y-3">
        {MODES.map((m) => (
          <SelectableCard
            key={m.id}
            selected={domain.mode === m.id}
            onClick={() => setMode(m.id)}
            className="w-full"
          >
            <p className="text-sm font-medium">{m.label}</p>
            <p className="mt-1 text-xs text-muted-foreground">{m.hint}</p>
          </SelectableCard>
        ))}
      </div>

      {domain.mode === "subdomain" && (
        <div className="rounded-md border border-border bg-muted/40 p-4 text-sm">
          Your store will be live at{" "}
          <span className="font-medium text-foreground">{domain.domain}</span>.
        </div>
      )}

      {domain.mode === "byo" && (
        <div className="space-y-3">
          <div>
            <Label htmlFor="byo">Your domain</Label>
            <Input
              id="byo"
              value={domain.domain}
              onChange={(e) => { connectByo(e.target.value.trim()); setDnsConfigured(false); setEntriError(null); }}
              placeholder="yourstore.com"
            />
          </div>
          {domain.domain.trim() && (
            <div className="space-y-3">
              {dnsConfigured ? (
                <div className="flex items-center gap-2 rounded-md border border-success/40 bg-success/10 p-4 text-sm">
                  <CheckCircle2 className="h-4 w-4 text-success" />
                  <span>DNS configured — propagation usually takes a few minutes.</span>
                </div>
              ) : (
                <div className="rounded-md border border-border p-4 space-y-3">
                  <p className="text-sm font-medium">Connect your DNS</p>
                  <p className="text-xs text-muted-foreground">
                    Let us auto-configure your DNS records, or add them manually below.
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={connectWithEntri}
                    disabled={entriLoading}
                    className="flex items-center gap-2"
                  >
                    <Settings2 className="h-4 w-4" />
                    {entriLoading ? "Opening widget…" : "Auto-configure DNS"}
                  </Button>
                  {entriError && <p className="text-xs text-destructive">{entriError}</p>}
                </div>
              )}

              {!dnsConfigured && (
                <details className="rounded-md border border-border">
                  <summary className="cursor-pointer px-4 py-3 text-sm font-medium select-none">
                    Or add records manually
                  </summary>
                  <div className="px-4 pb-4">
                    <p className="mb-3 text-xs text-muted-foreground">
                      Add these records at your DNS provider. We'll verify automatically once they propagate.
                    </p>
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead className="text-muted-foreground">
                          <tr>
                            <th className="pb-1 pr-4">Type</th>
                            <th className="pb-1 pr-4">Name</th>
                            <th className="pb-1">Value</th>
                          </tr>
                        </thead>
                        <tbody className="font-mono">
                          {domain.dnsRecords.map((r) => (
                            <tr key={r.type + r.name} className="border-t border-border">
                              <td className="py-1 pr-4">{r.type}</td>
                              <td className="py-1 pr-4">{r.name}</td>
                              <td className="py-1">{r.value}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </details>
              )}
            </div>
          )}
        </div>
      )}

      {domain.mode === "buy" && (
        <div className="space-y-3">
          <div>
            <Label htmlFor="search">Search for a domain</Label>
            <div className="flex gap-2">
              <Input
                id="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="yourstore.com"
                onKeyDown={(e) => e.key === "Enter" && query.trim() && check()}
              />
              <Button variant="outline" onClick={check} disabled={!query.trim() || checking}>
                {checking ? "Checking…" : "Check"}
              </Button>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              Tip: try one with &ldquo;taken&rdquo; to see the unavailable state.
            </p>
          </div>

          {result && !domain.purchased && (
            <div className="flex items-center justify-between rounded-md border border-border p-4 text-sm">
              <span className="flex items-center gap-2">
                {result.available ? (
                  <CheckCircle2 className="h-4 w-4 text-success" />
                ) : (
                  <XCircle className="h-4 w-4 text-destructive" />
                )}
                <span className="font-medium">{result.domain}</span>
                <span className="text-muted-foreground">
                  {result.available
                    ? `available — ₹${(result.priceMinor / 100).toFixed(0)}/yr`
                    : "not available"}
                </span>
              </span>
              {result.available && (
                <Button size="sm" onClick={buy} disabled={buying}>
                  {buying ? "Registering…" : "Buy & connect"}
                </Button>
              )}
            </div>
          )}

          {domain.purchased && (
            <div className="flex items-center gap-2 rounded-md border border-success/40 bg-success/10 p-4 text-sm">
              <CheckCircle2 className="h-4 w-4 text-success" />
              <span>
                <span className="font-medium">{domain.domain}</span> registered and connected
                automatically.
              </span>
            </div>
          )}
        </div>
      )}
    </StepShell>
  );
}
