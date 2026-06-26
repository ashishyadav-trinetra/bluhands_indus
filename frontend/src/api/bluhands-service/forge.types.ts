// TypeScript types mirroring the control-plane Pydantic schemas.
// Keep in sync with control-plane/app/schemas/.

export type Industry = "ecommerce" | "crm" | "restaurant" | "erp" | "healthcare";
export type IsolationLevel = "pooled" | "schema" | "siloed";
export type TenantStatus = "created" | "provisioning" | "active" | "suspended" | "deleted";

export type BuildStatus =
  | "queued"
  | "provisioning"
  | "building"
  | "testing"
  | "review"
  | "live"
  | "updating"
  | "failed"
  | "cancelled";

export interface UserView {
  id: string;
  email: string;
  full_name: string | null;
  is_platform_admin: boolean;
  created_at: string;
}

export interface MembershipView {
  org_id: string;
  organization_name: string;
  role: string;
}

export interface MeResponse {
  user: UserView;
  memberships: MembershipView[];
}

export interface TenantCreate {
  industry: Industry;
  isolation_level?: IsolationLevel;
  display_name?: string;
  region?: string;
}

export interface TenantResponse {
  id: string;
  org_id: string;
  industry: Industry;
  isolation_level: IsolationLevel;
  status: TenantStatus;
  display_name: string | null;
  region: string;
  created_at: string;
  updated_at: string;
}

export interface BuildStartRequest {
  prompt: string;
  idempotency_key?: string;
  // GitHub (optional, user-driven)
  github_repo_url?: string;
  github_branch?: string;
  github_push?: boolean;
  github_pull?: boolean;
}

export interface GithubStatus {
  connected: boolean;
}

export interface GithubRepo {
  name: string;
  full_name: string;
  private: boolean;
  clone_url: string;
}

export interface BuildRunResponse {
  id: string;
  tenant_id: string;
  status: BuildStatus;
  prompt: string | null;
  celery_task_id: string | null;
  credits_cost: number;
  preview_url: string | null;
  prod_url: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

// Control-plane wraps every response in this envelope.
export interface ForgeEnvelope<T> {
  success: boolean;
  data: T;
  meta?: Record<string, unknown>;
  request_id?: string;
}
