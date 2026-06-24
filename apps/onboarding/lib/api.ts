// Thin control-plane client. Two implementations behind one interface:
//   - MockApi: fully offline simulation (default) for dev + this build.
//   - HttpApi: real calls to the control plane.
// Components only ever see the `Api` interface, so going live is a config flip.

import type {
  Brand,
  Business,
  BuildState,
  Catalog,
  ClarifyAnswer,
  ClarifyResult,
  Domain,
  DomainAvailability,
  EnhanceResult,
  Industry,
  MeResult,
  StartBuildResult,
  TenantResult,
} from "./types";

export interface Api {
  /** Return the current user's org + admin flag (also JIT-provisions on Supabase path). */
  getMe(): Promise<MeResult>;
  createTenant(input: { industry: Industry; business: Business }, orgId: string): Promise<TenantResult>;
  checkDomain(domain: string): Promise<DomainAvailability>;
  purchaseDomain(domain: string): Promise<{ ok: true }>;
  /** Get a short-lived Entri session token for the BYO DNS-connect widget. */
  getDomainEntriSession(domain: string): Promise<{ token: string; applicationId: string; dnsRecords: { type: string; host: string; value: string; ttl: number }[] }>;
  clarify(input: {
    prompt: string;
    industry: Industry;
    brand?: Brand;
    business?: Business;
    products?: unknown[];
  }): Promise<ClarifyResult>;
  enhance(input: {
    prompt: string;
    industry: Industry;
    clarifications: ClarifyAnswer[];
  }): Promise<EnhanceResult>;
  startBuild(input: {
    tenantId: string;
    orgId: string;
    brand: Brand;
    catalog: Catalog;
    domain: Domain;
    clarifications?: ClarifyAnswer[];
    enhancedPrompt?: string;
  }): Promise<StartBuildResult>;
  getBuild(buildId: string, tenantId: string, orgId: string): Promise<BuildState>;
}

// --- Build sequence helpers (used by MockApi and tests) ---

import type { BuildStatus } from "./types";

export const BUILD_SEQUENCE: BuildState["status"][] = [
  "queued",
  "building",
  "building",
  "self_testing",
  "deploying",
  "live",
];

export function buildStateAt(
  buildId: string,
  poll: number,
  previewBase = "https://preview.bluhands.app",
): BuildState {
  const idx = Math.min(poll, BUILD_SEQUENCE.length - 1);
  const status = BUILD_SEQUENCE[idx];
  return {
    buildId,
    status,
    previewUrl: status === "live" ? `${previewBase}/${buildId}` : null,
    error: null,
  };
}

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));
const id = (prefix: string) => `${prefix}_${Math.random().toString(36).slice(2, 12)}`;

// --- MockApi ---

export class MockApi implements Api {
  private polls = new Map<string, number>();

  async getMe(): Promise<MeResult> {
    await delay(300);
    return { orgId: id("org"), isAdmin: false };
  }

  async createTenant(): Promise<TenantResult> {
    await delay(300);
    return { tenantId: id("ten") };
  }

  async checkDomain(domain: string): Promise<DomainAvailability> {
    await delay(500);
    const available = !/taken/i.test(domain);
    return { domain, available, priceMinor: 99900, currency: "INR" };
  }

  async purchaseDomain(): Promise<{ ok: true }> {
    await delay(700);
    return { ok: true };
  }

  async getDomainEntriSession(domain: string): Promise<{ token: string; applicationId: string; dnsRecords: { type: string; host: string; value: string; ttl: number }[] }> {
    await delay(300);
    return {
      token: "stub-entri-session",
      applicationId: "bluhands",
      dnsRecords: [
        { type: "A", host: "@", value: "76.76.21.21", ttl: 300 },
        { type: "CNAME", host: "www", value: "cname.bluhands.app", ttl: 300 },
        { type: "TXT", host: "_bluhands", value: `verify=${domain}`, ttl: 300 },
      ],
    };
  }

  async clarify(): Promise<ClarifyResult> {
    await delay(600);
    return {
      questions: [
        {
          id: "catalog_size",
          text: "How many products are you planning to list initially?",
          kind: "single",
          options: ["1–10", "11–50", "50+"],
          allow_other: false,
          help: "",
        },
        {
          id: "payment_methods",
          text: "Which payment methods should your store accept?",
          kind: "multi",
          options: ["UPI", "Credit/Debit card", "Net banking", "Cash on delivery"],
          allow_other: true,
          help: "",
        },
      ],
    };
  }

  async enhance(input: { prompt: string; industry: Industry }): Promise<EnhanceResult> {
    await delay(800);
    return {
      summary: `An e-commerce storefront for ${input.industry} with product catalog, cart, and checkout.`,
      app_type: "web",
      needs_auth: true,
      needs_database: true,
      integrations: ["payment gateway"],
      frontend_plan: ["Home/catalog page", "Product detail", "Cart", "Checkout", "Order confirmation"],
      enhanced_prompt: `Build a production-ready ${input.industry} storefront: ${input.prompt}`,
    };
  }

  async startBuild(): Promise<StartBuildResult> {
    await delay(300);
    const buildId = id("bld");
    this.polls.set(buildId, 0);
    return { buildId };
  }

  async getBuild(buildId: string): Promise<BuildState> {
    await delay(900);
    const poll = this.polls.get(buildId) ?? 0;
    this.polls.set(buildId, poll + 1);
    return buildStateAt(buildId, poll);
  }
}

// --- HttpApi ---

/**
 * Real client for the control plane. Auth token is set after Supabase login
 * via ``setToken()``. Endpoints:
 *   GET  /api/v1/auth/me
 *   POST /api/v1/orgs/{orgId}/tenants
 *   GET  /api/v1/domains/check
 *   POST /api/v1/domains/purchase
 *   POST /api/v1/agent/clarify
 *   POST /api/v1/agent/enhance
 *   POST /api/v1/orgs/{orgId}/tenants/{tenantId}/builds
 *   GET  /api/v1/orgs/{orgId}/tenants/{tenantId}/builds/{buildId}
 */
export class HttpApi implements Api {
  private _token: string | null = null;

  constructor(private readonly baseUrl: string) {}

  setToken(token: string): void {
    this._token = token;
  }

  private get authHeader(): Record<string, string> {
    if (!this._token) return {};
    return { Authorization: `Bearer ${this._token}` };
  }

  private async json<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...this.authHeader,
        ...(init?.headers ?? {}),
      },
    });
    const body = await res.json();
    if (!res.ok) throw new Error(body?.error?.message ?? `Request failed (${res.status})`);
    return (body.data ?? body) as T;
  }

  async getMe(): Promise<MeResult> {
    const data = await this.json<{
      user: { is_platform_admin: boolean };
      memberships: { org_id: string }[];
    }>("/api/v1/auth/me");
    const orgId = data.memberships[0]?.org_id;
    if (!orgId) throw new Error("No organisation found for this account");
    return { orgId, isAdmin: data.user.is_platform_admin };
  }

  async createTenant(
    input: { industry: Industry; business: Business },
    orgId: string,
  ): Promise<TenantResult> {
    const raw = await this.json<{ id: string }>(`/api/v1/orgs/${orgId}/tenants`, {
      method: "POST",
      body: JSON.stringify({
        industry: input.industry,
        display_name: input.business.storeName,
      }),
    });
    return { tenantId: raw.id };
  }

  checkDomain(domain: string): Promise<DomainAvailability> {
    return this.json(`/api/v1/domains/check?domain=${encodeURIComponent(domain)}`);
  }

  purchaseDomain(domain: string): Promise<{ ok: true }> {
    return this.json("/api/v1/domains/purchase", {
      method: "POST",
      body: JSON.stringify({ domain }),
    });
  }

  getDomainEntriSession(domain: string): Promise<{ token: string; applicationId: string; dnsRecords: { type: string; host: string; value: string; ttl: number }[] }> {
    return this.json("/api/v1/domains/entri-session", {
      method: "POST",
      body: JSON.stringify({ domain }),
    });
  }

  clarify(input: {
    prompt: string;
    industry: Industry;
    brand?: Brand;
    business?: Business;
    products?: unknown[];
  }): Promise<ClarifyResult> {
    return this.json("/api/v1/agent/clarify", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  enhance(input: {
    prompt: string;
    industry: Industry;
    clarifications: ClarifyAnswer[];
  }): Promise<EnhanceResult> {
    return this.json("/api/v1/agent/enhance", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  async startBuild(input: {
    tenantId: string;
    orgId: string;
    brand: Brand;
    catalog: Catalog;
    domain: Domain;
    clarifications?: ClarifyAnswer[];
    enhancedPrompt?: string;
  }): Promise<StartBuildResult> {
    // The control-plane BuildStartRequest takes only a prompt string.
    // Use the AI-enhanced prompt if available; fall back to a constructed summary.
    const prompt =
      input.enhancedPrompt ||
      `Build a ${input.brand.vibe ?? "modern"} ${input.catalog.choice === "sample" ? "sample catalog" : ""} storefront for ${input.brand.tagline || "this business"}. Domain: ${input.domain.domain}.`;

    const raw = await this.json<{ id: string }>(
      `/api/v1/orgs/${input.orgId}/tenants/${input.tenantId}/builds`,
      {
        method: "POST",
        body: JSON.stringify({
          prompt,
          custom_domain: input.domain.domain || undefined,
        }),
      },
    );
    return { buildId: raw.id };
  }

  async getBuild(buildId: string, tenantId: string, orgId: string): Promise<BuildState> {
    const raw = await this.json<{
      id: string;
      status: string;
      preview_url: string | null;
      prod_url: string | null;
      error: string | null;
    }>(`/api/v1/orgs/${orgId}/tenants/${tenantId}/builds/${buildId}`);

    // Map control-plane BuildStatus → onboarding BuildStatus.
    const statusMap: Record<string, BuildStatus> = {
      queued: "queued",
      provisioning: "building",
      building: "building",
      testing: "self_testing",
      review: "deploying",
      deploying: "deploying",
      live: "live",
      updating: "building",
      failed: "failed",
      cancelled: "failed",
    };

    return {
      buildId: raw.id,
      status: (statusMap[raw.status] ?? "building") as BuildStatus,
      previewUrl: raw.preview_url ?? raw.prod_url ?? null,
      error: raw.error,
    };
  }
}

// --- Singleton ---

let _api: Api | null = null;

/** Return the process-wide API instance. Mock unless NEXT_PUBLIC_USE_MOCK_API=false. */
export function getApi(): Api {
  if (_api) return _api;
  const useMock = process.env.NEXT_PUBLIC_USE_MOCK_API !== "false";
  const baseUrl = process.env.NEXT_PUBLIC_CONTROL_PLANE_URL ?? "http://localhost:8000";
  _api = useMock ? new MockApi() : new HttpApi(baseUrl);
  return _api;
}

/** Set the Supabase access token on the live HttpApi (no-op in mock mode). */
export function setApiToken(token: string): void {
  const api = getApi();
  if (api instanceof HttpApi) api.setToken(token);
}
