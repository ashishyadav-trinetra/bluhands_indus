/* eslint-disable i18next/no-literal-string */
/**
 * /connectors — Nango-powered integration marketplace.
 *
 * Lets merchants connect their store to external services (Stripe, Shopify,
 * HubSpot, etc.) via Nango's OAuth / API-key Connect UI.
 *
 * Flow:
 *  1. Click "Connect" → POST /api/v1/integrations/session (control-plane)
 *  2. Control-plane asks Nango for a session token scoped to this user
 *  3. Nango ConnectUI opens (modal) → user authorises the API
 *  4. Card flips to "Connected"
 */

import React from "react";
import { openHands } from "#/api/open-hands-axios";

// ── Integration catalog ───────────────────────────────────────────────────────

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

interface Integration {
  id: string;
  name: string;
  description: string;
  category: Category;
  domain: string;        // used for Clearbit logo fetch
  logoChar: string;      // fallback monogram
  badge?: "Popular" | "New";
}

const CATEGORIES: Category[] = [
  "All", "Payments", "Ecommerce", "Shipping",
  "Marketing", "CRM", "Accounting", "Messaging", "Productivity",
];

const INTEGRATIONS: Integration[] = [
  // Payments
  { id: "stripe", name: "Stripe", description: "Accept payments worldwide", category: "Payments", domain: "stripe.com", logoChar: "S", badge: "Popular" },
  { id: "razorpay", name: "Razorpay", description: "UPI, cards & wallets for India", category: "Payments", domain: "razorpay.com", logoChar: "R", badge: "Popular" },
  { id: "paddle", name: "Paddle", description: "Payments with tax handled automatically", category: "Payments", domain: "paddle.com", logoChar: "P" },
  { id: "chargebee", name: "Chargebee", description: "Subscription billing & revenue ops", category: "Payments", domain: "chargebee.com", logoChar: "C", badge: "New" },
  { id: "paypal", name: "PayPal", description: "Global wallet and card payments", category: "Payments", domain: "paypal.com", logoChar: "PP" },
  // Ecommerce
  { id: "shopify", name: "Shopify", description: "Import products & orders", category: "Ecommerce", domain: "shopify.com", logoChar: "S", badge: "Popular" },
  { id: "woocommerce", name: "WooCommerce", description: "Sync WordPress/WooCommerce catalog", category: "Ecommerce", domain: "woocommerce.com", logoChar: "W", badge: "New" },
  { id: "bigcommerce", name: "BigCommerce", description: "Connect your BigCommerce storefront", category: "Ecommerce", domain: "bigcommerce.com", logoChar: "B", badge: "New" },
  { id: "amazon-seller", name: "Amazon Seller", description: "Sync listings & fulfillment orders", category: "Ecommerce", domain: "amazon.com", logoChar: "A", badge: "New" },
  // Shipping
  { id: "shiprocket", name: "Shiprocket", description: "India's #1 shipping aggregator", category: "Shipping", domain: "shiprocket.in", logoChar: "SR", badge: "Popular" },
  { id: "fedex", name: "FedEx", description: "International shipping & tracking", category: "Shipping", domain: "fedex.com", logoChar: "F" },
  { id: "delhivery", name: "Delhivery", description: "Domestic B2B and B2C logistics", category: "Shipping", domain: "delhivery.com", logoChar: "D", badge: "New" },
  { id: "easypost", name: "EasyPost", description: "Multi-carrier shipping API", category: "Shipping", domain: "easypost.com", logoChar: "EP", badge: "New" },
  // Marketing
  { id: "mailchimp", name: "Mailchimp", description: "Email campaigns & automations", category: "Marketing", domain: "mailchimp.com", logoChar: "M", badge: "Popular" },
  { id: "klaviyo", name: "Klaviyo", description: "Email & SMS for ecommerce growth", category: "Marketing", domain: "klaviyo.com", logoChar: "K", badge: "Popular" },
  { id: "meta-ads", name: "Meta Ads", description: "Facebook & Instagram advertising", category: "Marketing", domain: "meta.com", logoChar: "M" },
  { id: "google-ads", name: "Google Ads", description: "Search & shopping campaigns", category: "Marketing", domain: "google.com", logoChar: "G" },
  { id: "brevo", name: "Brevo", description: "Transactional email & campaigns", category: "Marketing", domain: "brevo.com", logoChar: "B", badge: "New" },
  // CRM
  { id: "hubspot", name: "HubSpot", description: "CRM, contacts & sales pipeline", category: "CRM", domain: "hubspot.com", logoChar: "H", badge: "Popular" },
  { id: "salesforce", name: "Salesforce", description: "Enterprise CRM & automation", category: "CRM", domain: "salesforce.com", logoChar: "SF" },
  { id: "pipedrive", name: "Pipedrive", description: "Visual sales pipeline", category: "CRM", domain: "pipedrive.com", logoChar: "P", badge: "New" },
  { id: "zoho-crm", name: "Zoho CRM", description: "Omnichannel CRM", category: "CRM", domain: "zoho.com", logoChar: "Z", badge: "New" },
  // Accounting
  { id: "quickbooks", name: "QuickBooks", description: "Accounting, invoices & expenses", category: "Accounting", domain: "quickbooks.intuit.com", logoChar: "QB", badge: "Popular" },
  { id: "zoho-books", name: "Zoho Books", description: "Accounting & GST compliance", category: "Accounting", domain: "zoho.com", logoChar: "ZB" },
  { id: "xero", name: "Xero", description: "Cloud accounting for SMBs", category: "Accounting", domain: "xero.com", logoChar: "X", badge: "New" },
  // Messaging
  { id: "twilio", name: "Twilio SMS", description: "Programmatic SMS & voice", category: "Messaging", domain: "twilio.com", logoChar: "T", badge: "Popular" },
  { id: "whatsapp", name: "WhatsApp Business", description: "Order updates via WhatsApp", category: "Messaging", domain: "whatsapp.com", logoChar: "W", badge: "Popular" },
  { id: "sendgrid", name: "SendGrid", description: "Transactional email delivery", category: "Messaging", domain: "sendgrid.com", logoChar: "SG" },
  { id: "postmark", name: "Postmark", description: "Fast transactional email", category: "Messaging", domain: "postmarkapp.com", logoChar: "PM", badge: "New" },
  // Productivity
  { id: "google-sheets", name: "Google Sheets", description: "Sync orders to spreadsheets", category: "Productivity", domain: "google.com", logoChar: "GS", badge: "Popular" },
  { id: "notion", name: "Notion", description: "Push data to your workspace", category: "Productivity", domain: "notion.so", logoChar: "N", badge: "New" },
  { id: "slack", name: "Slack", description: "Order alerts & build notifications", category: "Productivity", domain: "slack.com", logoChar: "SL" },
  { id: "airtable", name: "Airtable", description: "Flexible database for products", category: "Productivity", domain: "airtable.com", logoChar: "AT", badge: "New" },
];

interface NangoConnection { provider_config_key: string; }

// ── Helpers ───────────────────────────────────────────────────────────────────

const LOGO_DEV_TOKEN = import.meta.env.VITE_LOGO_DEV_TOKEN as string | undefined;

/** Fetches the real brand logo via logo.dev; falls back to a monogram. */
function Logo({ intg }: { intg: Integration }) {
  const [failed, setFailed] = React.useState(false);
  const src = LOGO_DEV_TOKEN
    ? `https://img.logo.dev/${intg.domain}?token=${LOGO_DEV_TOKEN}&size=40&format=webp`
    : `https://www.google.com/s2/favicons?domain=${intg.domain}&sz=64`;

  if (!failed) {
    return (
      <div className="h-9 w-9 shrink-0 rounded-lg bg-white/[0.05] flex items-center justify-center overflow-hidden border border-white/[0.06]">
        <img
          src={src}
          alt={intg.name}
          width={22}
          height={22}
          className="object-contain"
          onError={() => setFailed(true)}
        />
      </div>
    );
  }

  // Fallback monogram — muted, not loud
  return (
    <div className="h-9 w-9 shrink-0 rounded-lg bg-white/[0.05] flex items-center justify-center border border-white/[0.06]">
      <span className="text-[11px] font-semibold text-[#6b7280] tracking-wide">
        {intg.logoChar}
      </span>
    </div>
  );
}

function Card({
  intg,
  connected,
  onConnect,
  busy,
}: {
  intg: Integration;
  connected: boolean;
  onConnect: (id: string) => void;
  busy: string | null;
}) {
  const isLoading = busy === intg.id;
  return (
    <div className="group relative flex flex-col gap-3.5 rounded-xl border border-white/[0.06] bg-[#111318] p-4 transition-all duration-150 hover:border-white/[0.10] hover:bg-[#141720]">
      {/* Badge — text only, top-right */}
      {intg.badge && (
        <span
          className={`absolute right-3 top-3 text-[9px] font-semibold uppercase tracking-widest ${
            intg.badge === "Popular" ? "text-[#60a5fa]" : "text-[#a78bfa]"
          }`}
        >
          {intg.badge}
        </span>
      )}

      {/* Logo + name */}
      <div className="flex items-center gap-3">
        <Logo intg={intg} />
        <div className="min-w-0">
          <p className="text-[13px] font-medium text-[#e2e8f0] leading-tight">{intg.name}</p>
          <p className="mt-0.5 text-[11px] text-[#4b5563] leading-snug line-clamp-2">{intg.description}</p>
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between pt-0.5">
        <span className="text-[10px] text-[#374151] font-medium tracking-wide uppercase">
          {intg.category}
        </span>
        {connected ? (
          <span className="flex items-center gap-1 text-[11px] font-medium text-[#34d399]">
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
              <circle cx="5" cy="5" r="4.5" stroke="#34d399" strokeWidth="1.2" />
              <path d="M2.8 5l1.6 1.6 2.8-2.8" stroke="#34d399" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Connected
          </span>
        ) : (
          <button
            type="button"
            onClick={() => onConnect(intg.id)}
            disabled={isLoading || !!busy}
            className="flex items-center gap-1.5 rounded-md border border-white/[0.08] bg-white/[0.04] px-2.5 py-1 text-[11px] font-medium text-[#94a3b8] transition-all hover:border-white/[0.15] hover:bg-white/[0.07] hover:text-white disabled:opacity-40"
          >
            {isLoading ? (
              <svg className="animate-spin h-2.5 w-2.5" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
            ) : (
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                <path d="M5 1v8M1 5h8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
              </svg>
            )}
            {isLoading ? "Opening…" : "Connect"}
          </button>
        )}
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ConnectorsPage() {
  const [activeCategory, setActiveCategory] = React.useState<Category>("All");
  const [search, setSearch] = React.useState("");
  const [showConnected, setShowConnected] = React.useState(false);
  const [connections, setConnections] = React.useState<NangoConnection[]>([]);
  const [busy, setBusy] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  // Load existing connections on mount
  React.useEffect(() => {
    openHands
      .get<{ connections?: NangoConnection[] }>("/api/v1/integrations/connections")
      .then((r) => { if (r.data.connections) setConnections(r.data.connections); })
      .catch(() => {}); // silently ignore if Nango not configured yet
  }, []);

  const connectedIds = new Set(connections.map((c) => c.provider_config_key));

  const filtered = INTEGRATIONS.filter((i) => {
    if (showConnected && !connectedIds.has(i.id)) return false;
    if (activeCategory !== "All" && i.category !== activeCategory) return false;
    if (search) {
      const q = search.toLowerCase();
      if (!i.name.toLowerCase().includes(q) && !i.description.toLowerCase().includes(q)) return false;
    }
    return true;
  });

  const countFor = (cat: Category) =>
    INTEGRATIONS.filter((i) => cat === "All" || i.category === cat).length;

  const handleConnect = async (integrationId: string) => {
    setBusy(integrationId);
    setError(null);
    try {
      // 1. Get Nango session token from control-plane
      const { data } = await openHands.post<{ session_token: string }>(
        "/api/v1/integrations/session",
        { integration_id: integrationId },
      );

      // 2. Dynamically import Nango SDK and open ConnectUI
      const { default: Nango } = await import("@nangohq/frontend");
      const nango = new Nango();
      await new Promise<void>((resolve, reject) => {
        const connect = nango.openConnectUI({
          onEvent: (event: { type: string; payload?: { connectionId?: string } }) => {
            if (event.type === "close") reject(new Error("cancelled"));
            if (event.type === "connect") {
              setConnections((prev) => [
                ...prev.filter((c) => c.provider_config_key !== integrationId),
                { provider_config_key: integrationId },
              ]);
              resolve();
            }
          },
        });
        connect.setSessionToken(data.session_token);
      });
    } catch (e) {
      if (e instanceof Error && e.message !== "cancelled") {
        setError(e.message || "Connection failed. Check Nango is configured.");
      }
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="flex h-full flex-col overflow-hidden bg-[#0c0e13]">
      {/* ── Header ── */}
      <div className="border-b border-white/[0.05] bg-[#0e1016] px-6 py-3.5">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-[13px] font-semibold text-[#e2e8f0] tracking-tight">Connectors</h1>
            <p className="text-[11px] text-[#3b4250] mt-0.5">{INTEGRATIONS.length} integrations available</p>
          </div>

          {/* Search */}
          <div className="relative max-w-[260px] flex-1">
            <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" width="12" height="12" viewBox="0 0 12 12" fill="none">
              <circle cx="5" cy="5" r="4" stroke="#3b4250" strokeWidth="1.4" />
              <line x1="8" y1="8" x2="11" y2="11" stroke="#3b4250" strokeWidth="1.4" strokeLinecap="round" />
            </svg>
            <input
              type="text"
              placeholder="Search integrations…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-7 w-full rounded-md border border-white/[0.06] bg-white/[0.03] pl-7 pr-3 text-[12px] text-[#94a3b8] placeholder-[#2d3340] outline-none focus:border-white/[0.12] focus:bg-white/[0.05] transition-colors"
            />
          </div>

          {/* Connected filter */}
          <button
            type="button"
            onClick={() => setShowConnected((v) => !v)}
            className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[11px] transition-colors ${
              showConnected
                ? "border-[#34d399]/30 bg-[#34d399]/5 text-[#34d399]"
                : "border-white/[0.06] text-[#4b5563] hover:border-white/[0.10] hover:text-[#94a3b8]"
            }`}
          >
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
              <circle cx="5" cy="5" r="4.5" stroke="currentColor" strokeWidth="1.2" />
              <path d="M2.8 5l1.6 1.6 2.8-2.8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Connected ({connections.length})
          </button>
        </div>
      </div>

      {error && (
        <div className="mx-5 mt-3 flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/5 px-3.5 py-2 text-[11px] text-red-400/80">
          <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
            <circle cx="5.5" cy="5.5" r="5" stroke="currentColor" strokeWidth="1.1" />
            <path d="M5.5 3v3M5.5 7.5h.01" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" />
          </svg>
          {error}
          <button type="button" onClick={() => setError(null)} className="ml-auto opacity-60 hover:opacity-100">
            <svg width="9" height="9" viewBox="0 0 9 9" fill="none">
              <path d="M1.5 1.5l6 6M7.5 1.5l-6 6" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
            </svg>
          </button>
        </div>
      )}

      <div className="flex min-h-0 flex-1 gap-0">
        {/* ── Category sidebar ── */}
        <div className="w-40 shrink-0 border-r border-white/[0.04] overflow-y-auto px-2 py-4">
          <p className="mb-2 px-2 text-[9px] font-semibold uppercase tracking-[0.12em] text-[#2d3340]">Categories</p>
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              type="button"
              onClick={() => setActiveCategory(cat)}
              className={`flex w-full items-center justify-between rounded-md px-2.5 py-1.5 text-[12px] mb-px transition-colors ${
                activeCategory === cat
                  ? "bg-white/[0.06] text-[#cbd5e1] font-medium"
                  : "text-[#374151] hover:bg-white/[0.03] hover:text-[#64748b]"
              }`}
            >
              <span>{cat}</span>
              <span className={`text-[10px] tabular-nums ${activeCategory === cat ? "text-[#4b5563]" : "text-[#1f2937]"}`}>
                {countFor(cat)}
              </span>
            </button>
          ))}

          {connectedIds.size > 0 && (
            <div className="mt-4 mx-1 rounded-lg border border-[#34d399]/10 bg-[#34d399]/[0.03] p-2.5">
              <p className="text-[9px] font-semibold uppercase tracking-widest text-[#34d399]/60 mb-2">
                {connectedIds.size} connected
              </p>
              {[...connectedIds].map((id) => {
                const intg = INTEGRATIONS.find((i) => i.id === id);
                return intg ? (
                  <p key={id} className="flex items-center gap-1.5 text-[10px] text-[#34d399]/50 mb-1">
                    <span className="text-[8px]">✓</span>
                    {intg.name}
                  </p>
                ) : null;
              })}
            </div>
          )}
        </div>

        {/* ── Grid ── */}
        <div className="flex-1 overflow-y-auto px-4 py-4">
          <p className="mb-3 text-[10px] text-[#2d3340] tracking-wide">
            {filtered.length} result{filtered.length !== 1 ? "s" : ""}
            {activeCategory !== "All" ? ` · ${activeCategory}` : ""}
            {search ? ` · "${search}"` : ""}
          </p>

          {filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-white/[0.04] py-20 text-center">
              <svg width="28" height="28" viewBox="0 0 28 28" fill="none" className="opacity-10">
                <path d="M3 14h5M20 14h5M14 3v5M14 20v5" stroke="#9099ac" strokeWidth="1.8" strokeLinecap="round" />
                <circle cx="14" cy="14" r="4.5" stroke="#9099ac" strokeWidth="1.8" />
              </svg>
              <p className="text-[11px] text-[#374151]">No integrations found</p>
              <button
                type="button"
                onClick={() => { setSearch(""); setActiveCategory("All"); setShowConnected(false); }}
                className="text-[11px] text-[#4b5563] hover:text-[#94a3b8] mt-1 transition-colors"
              >
                Clear filters
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {filtered.map((intg) => (
                <Card
                  key={intg.id}
                  intg={intg}
                  connected={connectedIds.has(intg.id)}
                  onConnect={handleConnect}
                  busy={busy}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
