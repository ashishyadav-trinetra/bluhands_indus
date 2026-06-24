import React from "react";
import { useNavigate } from "react-router";
import { openHands } from "#/api/open-hands-axios";

// ── Plan configuration ──────────────────────────────────────────────────────

interface PlanConfig {
  id: string;
  name: string;
  monthlyPrice: number | "custom";
  annualPrice?: number;
  creditsLabel: string;
  features: string[];
  highlight?: boolean;
  cta: string;
}

const PLANS: PlanConfig[] = [
  {
    id: "free",
    name: "Free",
    monthlyPrice: 0,
    creditsLabel: "5 daily credits (up to 30/month)",
    features: [
      "Bring your own API key",
      "1 workspace member",
      "Community support",
      "All open-source features",
    ],
    cta: "Current plan",
  },
  {
    id: "pro",
    name: "Pro",
    monthlyPrice: 5,
    annualPrice: 48,
    creditsLabel: "20 credits / month",
    highlight: true,
    features: [
      "Everything in Free",
      "20 monthly managed credits",
      "Up to 5 workspace members",
      "Priority task queue",
      "File export",
      "Email support",
    ],
    cta: "Upgrade to Pro",
  },
  {
    id: "business",
    name: "Business",
    monthlyPrice: 50,
    annualPrice: 480,
    creditsLabel: "100 credits / month",
    features: [
      "Everything in Pro",
      "100 monthly managed credits",
      "Up to 50 workspace members",
      "Audit logs",
      "SSO / SAML",
      "Dedicated support",
    ],
    cta: "Upgrade to Business",
  },
  {
    id: "enterprise",
    name: "Enterprise",
    monthlyPrice: "custom",
    creditsLabel: "Unlimited credits",
    features: [
      "Everything in Business",
      "Unlimited workspace members",
      "Volume-based credit pricing",
      "Custom domain",
      "SLA guarantee",
      "Dedicated CSM",
    ],
    cta: "Book a demo",
  },
];

// ── PricingCard ─────────────────────────────────────────────────────────────

interface PricingCardProps {
  plan: PlanConfig;
  isAnnual: boolean;
  currentPlan: string;
  onUpgrade: (planId: string) => void;
  loading: boolean;
}

function PricingCard({
  plan,
  isAnnual,
  currentPlan,
  onUpgrade,
  loading,
}: PricingCardProps) {
  const isCurrent = plan.id === currentPlan;
  const price =
    plan.monthlyPrice === "custom"
      ? null
      : isAnnual && plan.annualPrice !== undefined
        ? Math.round(plan.annualPrice / 12)
        : plan.monthlyPrice;

  return (
    <div
      className={`
        relative flex flex-col rounded-2xl border p-6 transition-all duration-200
        ${
          plan.highlight
            ? "border-[#7C3AED] bg-[#1a1040] shadow-[0_0_30px_rgba(124,58,237,0.2)]"
            : "border-[#2a2d37] bg-[#111318]"
        }
      `}
    >
      {plan.highlight && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2">
          <span className="rounded-full bg-[#7C3AED] px-3 py-1 text-xs font-semibold text-white">
            Most popular
          </span>
        </div>
      )}

      {/* Plan name */}
      <h3 className="text-lg font-semibold text-white">{plan.name}</h3>

      {/* Description */}
      <p className="mt-1 text-sm text-[#94a3b8]">
        {plan.id === "free" && "Get started for free, bring your own key."}
        {plan.id === "pro" &&
          "Designed for fast-moving teams building together."}
        {plan.id === "business" && "Advanced controls for growing departments."}
        {plan.id === "enterprise" &&
          "Built for large orgs needing scale & governance."}
      </p>

      {/* Price */}
      <div className="mt-5">
        {plan.monthlyPrice === "custom" ? (
          <div className="text-3xl font-bold text-white">Platform fee</div>
        ) : (
          <div className="flex items-end gap-1">
            <span className="text-4xl font-bold text-white">${price}</span>
            <span className="mb-1 text-sm text-[#64748b]">/ month</span>
          </div>
        )}
        {isAnnual && plan.annualPrice && (
          <p className="mt-1 text-xs text-[#22c55e]">
            Billed annually (${plan.annualPrice}/yr) · Save{" "}
            {Math.round(
              100 -
                (plan.annualPrice / ((plan.monthlyPrice as number) * 12)) * 100,
            )}
            %
          </p>
        )}
      </div>

      {/* Credits */}
      <div className="mt-4 rounded-lg bg-[#0f172a] px-3 py-2">
        <div className="flex items-center justify-between">
          <span className="text-sm text-[#94a3b8]">Credits</span>
          <span className="text-sm font-medium text-[#e2e8f0]">
            {plan.creditsLabel}
          </span>
        </div>
      </div>

      {/* CTA Button */}
      <button
        type="button"
        disabled={isCurrent || loading}
        onClick={() => onUpgrade(plan.id)}
        className={`
          mt-5 w-full rounded-xl py-2.5 text-sm font-semibold transition-all
          ${
            isCurrent
              ? "cursor-default bg-[#1e293b] text-[#64748b]"
              : plan.highlight
                ? "bg-[#7C3AED] text-white hover:bg-[#6d28d9]"
                : "border border-[#2a2d37] bg-transparent text-white hover:bg-[#1e293b]"
          }
          disabled:opacity-60
        `}
      >
        {isCurrent ? "✓ Current plan" : plan.cta}
      </button>

      {/* Feature list */}
      <ul className="mt-6 space-y-2.5">
        {plan.features.map((f) => (
          <li key={f} className="flex items-start gap-2 text-sm text-[#cbd5e1]">
            <svg
              className="mt-0.5 h-4 w-4 shrink-0 text-[#22c55e]"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
            {f}
          </li>
        ))}
      </ul>
    </div>
  );
}

// ── Pricing Page ─────────────────────────────────────────────────────────────

export default function PricingPage() {
  const navigate = useNavigate();
  const [isAnnual, setIsAnnual] = React.useState(false);
  const [currentPlan, setCurrentPlan] = React.useState("free");
  const [loading, setLoading] = React.useState(false);

  // Fetch the user's current plan on mount
  React.useEffect(() => {
    openHands
      .get("/api/billing/subscription-status")
      .then((res) => setCurrentPlan(res.data.plan ?? "free"))
      .catch(() => {});
  }, []);

  const handleUpgrade = async (planId: string) => {
    if (planId === "free" || planId === currentPlan) return;

    if (planId === "enterprise") {
      window.open(
        "mailto:sales@bluhands.ai?subject=Enterprise inquiry",
        "_blank",
      );
      return;
    }

    setLoading(true);
    try {
      const res = await openHands.post("/api/billing/subscription-checkout", {
        plan: planId,
        interval: isAnnual ? "year" : "month",
      });
      window.location.href = res.data.redirect_url;
    } catch (err: unknown) {
      console.error("Checkout error:", err);
      alert("Could not start checkout. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen px-4 py-16" style={{ background: "#0c0e10" }}>
      {/* Back link */}
      <button
        type="button"
        onClick={() => navigate(-1)}
        className="mb-8 flex items-center gap-2 text-sm text-[#64748b] hover:text-white"
      >
        ← Back
      </button>

      {/* Header */}
      <div className="mx-auto max-w-4xl text-center">
        <h1 className="text-4xl font-bold text-white">Plans &amp; credits</h1>
        <p className="mt-3 text-[#94a3b8]">
          Manage your subscription plan and credit balance.
        </p>

        {/* Annual toggle */}
        <div className="mt-8 flex items-center justify-center gap-3">
          <span
            className={`text-sm ${!isAnnual ? "text-white" : "text-[#64748b]"}`}
          >
            Monthly
          </span>
          <button
            type="button"
            role="switch"
            aria-checked={isAnnual}
            onClick={() => setIsAnnual((v) => !v)}
            className={`
              relative inline-flex h-6 w-11 items-center rounded-full transition-colors
              ${isAnnual ? "bg-[#7C3AED]" : "bg-[#334155]"}
            `}
          >
            <span
              className={`
                inline-block h-4 w-4 transform rounded-full bg-white transition-transform
                ${isAnnual ? "translate-x-6" : "translate-x-1"}
              `}
            />
          </button>
          <span
            className={`text-sm ${isAnnual ? "text-white" : "text-[#64748b]"}`}
          >
            Annual{" "}
            <span className="rounded-full bg-[#14532d] px-2 py-0.5 text-xs text-[#22c55e]">
              Save up to 20%
            </span>
          </span>
        </div>
      </div>

      {/* Cards grid */}
      <div className="mx-auto mt-12 grid max-w-6xl grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {PLANS.map((plan) => (
          <PricingCard
            key={plan.id}
            plan={plan}
            isAnnual={isAnnual}
            currentPlan={currentPlan}
            onUpgrade={handleUpgrade}
            loading={loading}
          />
        ))}
      </div>

      {/* FAQ */}
      <div className="mx-auto mt-20 max-w-2xl">
        <h2 className="mb-6 text-center text-2xl font-semibold text-white">
          Frequently asked questions
        </h2>
        {[
          {
            q: "What are credits?",
            a: "Credits are consumed when you use managed AI models through Blu Hands. Each conversation costs approximately 0.1–1 credit depending on length. Bring-your-own-key (BYOK) usage does not consume credits.",
          },
          {
            q: "Can I upgrade or downgrade anytime?",
            a: "Yes. Upgrades take effect immediately. Downgrades take effect at the end of your current billing period so you never lose access you've already paid for.",
          },
          {
            q: "What happens if I run out of credits?",
            a: "Your AI agent pauses until you top up credits or upgrade your plan. You can always continue using bring-your-own-key (BYOK) mode with no limits.",
          },
          {
            q: "Do unused credits roll over?",
            a: "Credits reset each billing cycle. Top-up credits (one-off purchases) do not expire.",
          },
        ].map(({ q, a }) => (
          <details key={q} className="group border-b border-[#1e293b] py-4">
            <summary className="flex cursor-pointer list-none items-center justify-between text-sm font-medium text-white">
              {q}
              <svg
                className="h-4 w-4 shrink-0 text-[#64748b] transition-transform group-open:rotate-180"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            </summary>
            <p className="mt-3 text-sm leading-relaxed text-[#94a3b8]">{a}</p>
          </details>
        ))}
      </div>

      {/* Footer CTA */}
      <div className="mx-auto mt-16 max-w-xl text-center">
        <p className="text-sm text-[#64748b]">
          Need something custom?{" "}
          <a
            href="mailto:sales@bluhands.ai"
            className="text-[#7C3AED] hover:underline"
          >
            Talk to sales
          </a>
        </p>
      </div>
    </div>
  );
}
