// Shared types for the onboarding flow. The request/response shapes mirror the
// control-plane API so swapping the mock client for the real one is a drop-in.

export type Industry = "ecommerce" | "crm" | "restaurant" | "erp" | "healthcare";

export type CatalogChoice = "sample" | "import" | "scratch";

export type DomainMode = "byo" | "buy" | "subdomain";

/** Build lifecycle, mirrors control-plane BuildStatus. */
export type BuildStatus =
  | "queued"
  | "building"
  | "self_testing"
  | "deploying"
  | "live"
  | "failed";

export interface Account {
  fullName: string;
  email: string;
  /** NOTE: password is intentionally NOT stored here — it lives only in
   *  local component state and is consumed immediately by Supabase signUp(). */
  organizationName: string;
}

export interface Business {
  storeName: string;
  category: string;
  country: string; // ISO-2, e.g. "IN"
  currency: string; // ISO-4217, e.g. "INR"
  supportEmail: string;
}

export interface Brand {
  tagline: string;
  primaryColor: string; // hex
  accentColor: string; // hex
  vibe: string; // e.g. "minimal", "playful", "premium"
  logoName: string | null; // file name only (upload is stubbed)
}

export interface Product {
  id: string;
  name: string;
  price: string; // raw input, formatted/validated server-side
  stock: string; // raw input, formatted/validated server-side
  images: string[]; // file names only (upload is stubbed)
}

export interface Catalog {
  choice: CatalogChoice;
  products: Product[];
}

export interface DnsRecord {
  type: string;
  name: string;
  value: string;
}

export interface Domain {
  mode: DomainMode;
  domain: string; // chosen/owned domain or the platform subdomain
  // BYO: records the merchant must add. Buy: empty (entri auto-configures).
  dnsRecords: DnsRecord[];
  purchased: boolean;
}

/** The full state collected across the wizard. */
export interface OnboardingData {
  industry: Industry;
  account: Account;
  business: Business;
  brand: Brand;
  catalog: Catalog;
  domain: Domain;
}

// --- API payloads (mirror control-plane endpoints) ---

export interface RegisterResult {
  accessToken: string;
  orgId: string;
}

/** From GET /api/v1/auth/me */
export interface MeResult {
  orgId: string;
  isAdmin: boolean;
}

/** A single clarifying question from the agent. */
export interface ClarifyQuestion {
  id: string;
  text: string;
  kind: "single" | "multi" | "text";
  options: string[];
  allow_other: boolean;
  help: string;
}

/** An answer to one clarifying question (mirrors agent Answer schema). */
export interface ClarifyAnswer {
  question_id: string;
  selected: string[];
  other?: string;
}

/** From POST /api/v1/agent/clarify */
export interface ClarifyResult {
  questions: ClarifyQuestion[];
}

/** From POST /api/v1/agent/enhance */
export interface EnhanceResult {
  summary: string;
  app_type: string;
  needs_auth: boolean;
  needs_database: boolean;
  integrations: string[];
  frontend_plan: string[];
  enhanced_prompt: string;
}

export interface TenantResult {
  tenantId: string;
}

export interface StartBuildResult {
  buildId: string;
}

export interface BuildState {
  buildId: string;
  status: BuildStatus;
  previewUrl: string | null;
  error: string | null;
}

export interface DomainAvailability {
  domain: string;
  available: boolean;
  priceMinor: number; // in minor currency units
  currency: string;
}
