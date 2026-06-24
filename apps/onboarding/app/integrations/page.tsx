"use client";

/**
 * /integrations — Nango-powered integration marketplace.
 *
 * Lets merchants connect their store to 800+ external APIs (Stripe, Shopify,
 * HubSpot, Mailchimp, etc.) via Nango's OAuth / API-key Connect UI.
 *
 * Flow:
 *   1. Click "Connect" → frontend calls POST /api/v1/integrations/session
 *   2. Control-plane asks Nango for a session token scoped to this user
 *   3. Nango ConnectUI opens (modal) → user authorises the API
 *   4. Nango fires webhook → control-plane logs the connection
 *   5. Page refreshes connection list → card shows "Connected"
 */

import { useEffect, useState } from "react";
import { CheckCircle2, ChevronRight, Loader2, PlugZap, RefreshCw, Search, X } from "lucide-react";
import Nango from "@nangohq/frontend";
import { supabase } from "@/lib/supabase";

// ── Integration catalog ──────────────────────────────────────────────────────

export interface Integration {
  id: string;          // Nango integration ID (unique_key in your Nango project)
  name: string;
  description: string;
  category: Category;
  logoChar: string;    // Fallback — first letter(s) used as avatar
  logoColor: string;   // Tailwind bg class for the avatar
  isNew?: boolean;
  popular?: boolean;
}

type Category =
  | "All"
  | "Payments"
  | "Ecommerce"
  | "Shipping"
  | "Marketing"
  | "CRM"
  | "Accounting"
  | "Messaging"
  | "Productivity";

const CATEGORIES: Category[] = [
  "All", "Payments", "Ecommerce", "Shipping",
  "Marketing", "CRM", "Accounting", "Messaging", "Productivity",
];

const INTEGRATIONS: Integration[] = [
  // Payments
  { id: "stripe", name: "Stripe", description: "Accept payments from customers worldwide", category: "Payments", logoChar: "S", logoColor: "bg-[#635bff]", popular: true },
  { id: "razorpay", name: "Razorpay", description: "India's leading payment gateway — UPI, cards, wallets", category: "Payments", logoChar: "R", logoColor: "bg-[#3395ff]", popular: true },
  { id: "paddle", name: "Paddle", description: "Payments with tax handled automatically", category: "Payments", logoChar: "P", logoColor: "bg-[#38a169]" },
  { id: "chargebee", name: "Chargebee", description: "Subscription billing and revenue management", category: "Payments", logoChar: "C", logoColor: "bg-[#f6854b]", isNew: true },
  { id: "paypal", name: "PayPal", description: "Global wallet and card payments", category: "Payments", logoChar: "PP", logoColor: "bg-[#003087]" },

  // Ecommerce
  { id: "shopify", name: "Shopify", description: "Import products and orders from your Shopify store", category: "Ecommerce", logoChar: "S", logoColor: "bg-[#96bf48]", popular: true },
  { id: "woocommerce", name: "WooCommerce", description: "Sync with WordPress/WooCommerce catalog", category: "Ecommerce", logoChar: "W", logoColor: "bg-[#7f54b3]", isNew: true },
  { id: "magento", name: "Adobe Commerce", description: "Enterprise ecommerce platform (Magento)", category: "Ecommerce", logoChar: "M", logoColor: "bg-[#e22b2b]", isNew: true },
  { id: "bigcommerce", name: "BigCommerce", description: "Connect your BigCommerce storefront", category: "Ecommerce", logoChar: "B", logoColor: "bg-[#121118]", isNew: true },
  { id: "amazon-seller", name: "Amazon Seller", description: "Sync Amazon listings and fulfillment orders", category: "Ecommerce", logoChar: "A", logoColor: "bg-[#ff9900]", isNew: true },

  // Shipping
  { id: "shiprocket", name: "Shiprocket", description: "India's #1 shipping aggregator — 25+ couriers", category: "Shipping", logoChar: "SR", logoColor: "bg-[#e91e63]", popular: true },
  { id: "fedex", name: "FedEx", description: "International shipping and tracking", category: "Shipping", logoChar: "F", logoColor: "bg-[#4d148c]" },
  { id: "delhivery", name: "Delhivery", description: "Domestic B2B and B2C logistics", category: "Shipping", logoChar: "D", logoColor: "bg-[#e53935]", isNew: true },
  { id: "easypost", name: "EasyPost", description: "Multi-carrier shipping API", category: "Shipping", logoChar: "EP", logoColor: "bg-[#19c1d5]", isNew: true },

  // Marketing
  { id: "mailchimp", name: "Mailchimp", description: "Email campaigns, audiences, and automations", category: "Marketing", logoChar: "M", logoColor: "bg-[#ffe01b] text-black", popular: true },
  { id: "klaviyo", name: "Klaviyo", description: "Email and SMS for ecommerce growth", category: "Marketing", logoChar: "K", logoColor: "bg-[#1a1919]", popular: true },
  { id: "meta-ads", name: "Meta Ads", description: "Facebook & Instagram advertising", category: "Marketing", logoChar: "M", logoColor: "bg-[#0081fb]" },
  { id: "google-ads", name: "Google Ads", description: "Search and shopping campaigns", category: "Marketing", logoChar: "G", logoColor: "bg-[#4285f4]" },
  { id: "brevo", name: "Brevo", description: "Transactional email and marketing campaigns", category: "Marketing", logoChar: "B", logoColor: "bg-[#0b996e]", isNew: true },

  // CRM
  { id: "hubspot", name: "HubSpot", description: "CRM, contacts, and sales pipeline", category: "CRM", logoChar: "H", logoColor: "bg-[#ff7a59]", popular: true },
  { id: "salesforce", name: "Salesforce", description: "Enterprise CRM and automation", category: "CRM", logoChar: "SF", logoColor: "bg-[#00a1e0]" },
  { id: "pipedrive", name: "Pipedrive", description: "Visual sales pipeline and deal management", category: "CRM", logoChar: "P", logoColor: "bg-[#1a1a1a]", isNew: true },
  { id: "zoho-crm", name: "Zoho CRM", description: "Omnichannel CRM for all business sizes", category: "CRM", logoChar: "Z", logoColor: "bg-[#e42527]", isNew: true },

  // Accounting
  { id: "quickbooks", name: "QuickBooks", description: "Accounting, invoices, and expense tracking", category: "Accounting", logoChar: "QB", logoColor: "bg-[#2ca01c]", popular: true },
  { id: "zoho-books", name: "Zoho Books", description: "Online accounting and GST compliance", category: "Accounting", logoChar: "ZB", logoColor: "bg-[#e42527]" },
  { id: "xero", name: "Xero", description: "Cloud accounting for small businesses", category: "Accounting", logoChar: "X", logoColor: "bg-[#13b5ea]", isNew: true },
  { id: "freshbooks", name: "FreshBooks", description: "Invoicing and time tracking", category: "Accounting", logoChar: "FB", logoColor: "bg-[#00b2e3]", isNew: true },

  // Messaging
  { id: "twilio", name: "Twilio SMS", description: "Programmatic SMS and voice calls", category: "Messaging", logoChar: "T", logoColor: "bg-[#f22f46]", popular: true },
  { id: "whatsapp", name: "WhatsApp Business", description: "Order updates and support via WhatsApp", category: "Messaging", logoChar: "W", logoColor: "bg-[#25d366]", popular: true },
  { id: "sendgrid", name: "SendGrid", description: "Transactional and marketing email delivery", category: "Messaging", logoChar: "SG", logoColor: "bg-[#1a82e2]" },
  { id: "postmark", name: "Postmark", description: "Fast, reliable transactional email", category: "Messaging", logoChar: "PM", logoColor: "bg-[#ffde00] text-black", isNew: true },

  // Productivity
  { id: "google-sheets", name: "Google Sheets", description: "Sync orders and inventory to spreadsheets", category: "Productivity", logoChar: "GS", logoColor: "bg-[#34a853]", popular: true },
  { id: "notion", name: "Notion", description: "Push data and notes to your Notion workspace", category: "Productivity", logoChar: "N", logoColor: "bg-[#000000]", isNew: true },
  { id: "slack", name: "Slack", description: "Order alerts and build notifications", category: "Productivity", logoChar: "SL", logoColor: "bg-[#4a154b]" },
  { id: "airtable", name: "Airtable", description: "Flexible database for products and orders", category: "Productivity", logoChar: "AT", logoColor: "bg-[#fcb400] text-black", isNew: true },
];

// ── Types ────────────────────────────────────────────────────────────────────

interface NangoConnection {
  connection_id: string;
  provider_config_key: string; // the integration ID
}

// ── Logo avatar ──────────────────────────────────────────────────────────────

function IntegrationLogo({ integration }: { integration: Integration }) {
  return (
    <div
      className={`flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl text-white text-sm font-bold shadow-sm ${integration.logoColor}`}
    >
      {integration.logoChar}
    </div>
  );
}

// ── Integration card ─────────────────────────────────────────────────────────

function IntegrationCard({
  integration,
  isConnected,
  onConnect,
  connecting,
}: {
  integration: Integration;
  isConnected: boolean;
  onConnect: (id: string) => void;
  connecting: string | null;
}) {
  const isLoading = connecting === integration.id;

  return (
    <div className="group relative flex flex-col gap-4 rounded-xl border border-border bg-card p-5 transition-all duration-200 hover:border-primary/30 hover:shadow-md">
      {/* Badge */}
      {(integration.isNew || integration.popular) && (
        <span className={`absolute right-4 top-4 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
          integration.popular
            ? "bg-primary/10 text-primary"
            : "bg-accent/10 text-accent-foreground"
        }`}>
          {integration.popular ? "Popular" : "New"}
        </span>
      )}

      <div className="flex items-start gap-3">
        <IntegrationLogo integration={integration} />
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-foreground">{integration.name}</p>
          <p className="mt-0.5 text-xs text-muted-foreground line-clamp-2">{integration.description}</p>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">
          {integration.category}
        </span>

        {isConnected ? (
          <span className="flex items-center gap-1 text-xs font-medium text-green-600">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Connected
          </span>
        ) : (
          <button
            onClick={() => onConnect(integration.id)}
            disabled={isLoading || !!connecting}
            className="flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {isLoading ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <PlugZap className="h-3 w-3" />
            )}
            {isLoading ? "Opening…" : "Connect"}
          </button>
        )}
      </div>
    </div>
  );
}

// ── Category sidebar item ────────────────────────────────────────────────────

function CategoryItem({
  category,
  count,
  active,
  onClick,
}: {
  category: Category;
  count: number;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm transition-colors ${
        active
          ? "bg-primary/10 font-medium text-primary"
          : "text-muted-foreground hover:bg-muted hover:text-foreground"
      }`}
    >
      <span>{category}</span>
      <span className={`text-xs ${active ? "text-primary/70" : "text-muted-foreground/60"}`}>
        {count}
      </span>
    </button>
  );
}

// ── Main page ────────────────────────────────────────────────────────────────

const CP_URL = process.env.NEXT_PUBLIC_CONTROL_PLANE_URL ?? "http://localhost:8000";

export default function IntegrationsPage() {
  const [activeCategory, setActiveCategory] = useState<Category>("All");
  const [search, setSearch] = useState("");
  const [showConnected, setShowConnected] = useState(false);
  const [connections, setConnections] = useState<NangoConnection[]>([]);
  const [connecting, setConnecting] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loadingAuth, setLoadingAuth] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Auth: get Supabase token on mount
  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setToken(data.session?.access_token ?? null);
      setLoadingAuth(false);
    });
  }, []);

  // Load connections when we have a token
  useEffect(() => {
    if (!token) return;
    fetch(`${CP_URL}/api/v1/integrations/connections`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        if (data?.connections) setConnections(data.connections);
      })
      .catch(() => {}); // silently ignore if Nango not configured
  }, [token]);

  const connectedIds = new Set(connections.map((c) => c.provider_config_key));

  // Filtered list
  const filtered = INTEGRATIONS.filter((i) => {
    if (showConnected && !connectedIds.has(i.id)) return false;
    if (activeCategory !== "All" && i.category !== activeCategory) return false;
    if (search && !i.name.toLowerCase().includes(search.toLowerCase()) && !i.description.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  // Category counts (against search filter only)
  const countFor = (cat: Category) =>
    INTEGRATIONS.filter((i) => {
      if (search && !i.name.toLowerCase().includes(search.toLowerCase())) return false;
      return cat === "All" || i.category === cat;
    }).length;

  const handleConnect = async (integrationId: string) => {
    if (!token) {
      setError("Sign in to connect integrations.");
      return;
    }
    setConnecting(integrationId);
    setError(null);
    try {
      // 1. Get session token from control-plane
      const res = await fetch(`${CP_URL}/api/v1/integrations/session`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ integration_id: integrationId }),
      });
      if (!res.ok) throw new Error("Failed to start integration session.");
      const { session_token } = await res.json();

      // 2. Open Nango ConnectUI
      const nango = new Nango();
      await new Promise<void>((resolve, reject) => {
        const connect = nango.openConnectUI({
          onEvent: (event) => {
            if (event.type === "close") reject(new Error("cancelled"));
            if (event.type === "connect") {
              setConnections((prev) => [
                ...prev.filter((c) => c.provider_config_key !== integrationId),
                { connection_id: event.payload?.connectionId ?? integrationId, provider_config_key: integrationId },
              ]);
              resolve();
            }
          },
        });
        connect.setSessionToken(session_token);
      });
    } catch (e) {
      if (e instanceof Error && e.message !== "cancelled") {
        setError(e.message);
      }
    } finally {
      setConnecting(null);
    }
  };

  if (loadingAuth) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* ── Top bar ── */}
      <div className="border-b border-border bg-card/50 px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <PlugZap className="h-4 w-4" />
            </div>
            <div>
              <h1 className="text-base font-semibold leading-none">Integrations</h1>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Connect your store to {INTEGRATIONS.length}+ apps
              </p>
            </div>
          </div>

          {/* Search */}
          <div className="relative max-w-sm flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search integrations…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-9 w-full rounded-lg border border-border bg-background pl-9 pr-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            />
            {search && (
              <button onClick={() => setSearch("")} className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          {/* Connected filter */}
          <button
            onClick={() => setShowConnected((v) => !v)}
            className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors ${
              showConnected
                ? "border-primary bg-primary/10 font-medium text-primary"
                : "border-border text-muted-foreground hover:border-primary/30 hover:text-foreground"
            }`}
          >
            <CheckCircle2 className="h-4 w-4" />
            Connected ({connections.length})
          </button>

          <button
            onClick={() => {
              if (!token) return;
              fetch(`${CP_URL}/api/v1/integrations/connections`, {
                headers: { Authorization: `Bearer ${token}` },
              })
                .then((r) => r.ok ? r.json() : null)
                .then((data) => { if (data?.connections) setConnections(data.connections); })
                .catch(() => {});
            }}
            className="rounded-lg border border-border p-2 text-muted-foreground hover:border-primary/30 hover:text-foreground"
            title="Refresh"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="mx-auto flex max-w-7xl gap-6 px-6 py-6">
        {/* ── Category sidebar ── */}
        <aside className="w-48 flex-shrink-0">
          <p className="mb-2 px-3 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
            Categories
          </p>
          <nav className="space-y-0.5">
            {CATEGORIES.map((cat) => (
              <CategoryItem
                key={cat}
                category={cat}
                count={countFor(cat)}
                active={activeCategory === cat}
                onClick={() => setActiveCategory(cat)}
              />
            ))}
          </nav>

          {connectedIds.size > 0 && (
            <div className="mt-6 rounded-xl border border-green-200 bg-green-50 p-3">
              <p className="text-xs font-medium text-green-800">
                {connectedIds.size} connected
              </p>
              <div className="mt-2 space-y-1">
                {[...connectedIds].slice(0, 5).map((id) => {
                  const intg = INTEGRATIONS.find((i) => i.id === id);
                  return intg ? (
                    <p key={id} className="flex items-center gap-1.5 text-xs text-green-700">
                      <CheckCircle2 className="h-3 w-3 flex-shrink-0" />
                      {intg.name}
                    </p>
                  ) : null;
                })}
                {connectedIds.size > 5 && (
                  <p className="text-xs text-green-600">+{connectedIds.size - 5} more</p>
                )}
              </div>
            </div>
          )}
        </aside>

        {/* ── Main grid ── */}
        <main className="min-w-0 flex-1">
          {error && (
            <div className="mb-4 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              <X className="h-4 w-4 flex-shrink-0" />
              {error}
              <button onClick={() => setError(null)} className="ml-auto">
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          )}

          <div className="mb-4 flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              {filtered.length} integration{filtered.length !== 1 ? "s" : ""}
              {activeCategory !== "All" ? ` in ${activeCategory}` : ""}
              {search ? ` matching "${search}"` : ""}
            </p>
          </div>

          {filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border py-20 text-center">
              <PlugZap className="h-10 w-10 text-muted-foreground/30" />
              <p className="text-sm font-medium text-muted-foreground">No integrations found</p>
              <p className="text-xs text-muted-foreground/70">Try a different category or search term</p>
              <button
                onClick={() => { setSearch(""); setActiveCategory("All"); setShowConnected(false); }}
                className="mt-1 text-xs text-primary hover:underline"
              >
                Clear filters
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {filtered.map((integration) => (
                <IntegrationCard
                  key={integration.id}
                  integration={integration}
                  isConnected={connectedIds.has(integration.id)}
                  onConnect={handleConnect}
                  connecting={connecting}
                />
              ))}
            </div>
          )}

          {!token && (
            <div className="mt-6 rounded-xl border border-primary/20 bg-primary/5 p-4 text-center">
              <p className="text-sm text-muted-foreground">
                <a href="/" className="font-medium text-primary hover:underline">Sign in</a>
                {" "}to connect integrations and manage credentials.
              </p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
