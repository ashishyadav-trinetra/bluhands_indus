import { forgeClient } from "./forge-axios";
import type {
  BuildRunResponse,
  BuildStartRequest,
  ForgeEnvelope,
  MeResponse,
  TenantCreate,
  TenantResponse,
} from "./forge.types";

function unwrap<T>(envelope: ForgeEnvelope<T>): T {
  if (!envelope.success) {
    // The control-plane error envelope may carry a message in `data` when
    // success is false. Surface it rather than returning bad data silently.
    const msg =
      typeof (envelope.data as Record<string, unknown>)?.message === "string"
        ? ((envelope.data as Record<string, unknown>).message as string)
        : "Control-plane request failed";
    throw new Error(msg);
  }
  return envelope.data;
}

export const forgeService = {
  // ── Identity ──────────────────────────────────────────────────────────────

  me: async (): Promise<MeResponse> => {
    const { data } = await forgeClient.get<ForgeEnvelope<MeResponse>>(
      "/api/v1/auth/me",
    );
    return unwrap(data);
  },

  // ── Tenants ───────────────────────────────────────────────────────────────

  listTenants: async (orgId: string): Promise<TenantResponse[]> => {
    const { data } = await forgeClient.get<ForgeEnvelope<TenantResponse[]>>(
      `/api/v1/orgs/${orgId}/tenants`,
    );
    return unwrap(data);
  },

  createTenant: async (
    orgId: string,
    body: TenantCreate,
  ): Promise<TenantResponse> => {
    const { data } = await forgeClient.post<ForgeEnvelope<TenantResponse>>(
      `/api/v1/orgs/${orgId}/tenants`,
      body,
    );
    return unwrap(data);
  },

  // ── Builds ────────────────────────────────────────────────────────────────

  startBuild: async (
    orgId: string,
    tenantId: string,
    body: BuildStartRequest,
  ): Promise<BuildRunResponse> => {
    const { data } = await forgeClient.post<ForgeEnvelope<BuildRunResponse>>(
      `/api/v1/orgs/${orgId}/tenants/${tenantId}/builds`,
      body,
    );
    return unwrap(data);
  },

  getBuild: async (
    orgId: string,
    tenantId: string,
    buildId: string,
  ): Promise<BuildRunResponse> => {
    const { data } = await forgeClient.get<ForgeEnvelope<BuildRunResponse>>(
      `/api/v1/orgs/${orgId}/tenants/${tenantId}/builds/${buildId}`,
    );
    return unwrap(data);
  },

  listBuilds: async (
    orgId: string,
    tenantId: string,
    skip = 0,
    limit = 20,
  ): Promise<BuildRunResponse[]> => {
    const { data } = await forgeClient.get<ForgeEnvelope<BuildRunResponse[]>>(
      `/api/v1/orgs/${orgId}/tenants/${tenantId}/builds`,
      { params: { skip, limit } },
    );
    return unwrap(data);
  },

  approveBuild: async (
    orgId: string,
    tenantId: string,
    buildId: string,
  ): Promise<BuildRunResponse> => {
    const { data } = await forgeClient.post<ForgeEnvelope<BuildRunResponse>>(
      `/api/v1/orgs/${orgId}/tenants/${tenantId}/builds/${buildId}/approve`,
      {},
      { headers: { "X-Confirm-Action": "true" } },
    );
    return unwrap(data);
  },

  cancelBuild: async (
    orgId: string,
    tenantId: string,
    buildId: string,
  ): Promise<BuildRunResponse> => {
    const { data } = await forgeClient.post<ForgeEnvelope<BuildRunResponse>>(
      `/api/v1/orgs/${orgId}/tenants/${tenantId}/builds/${buildId}/cancel`,
      {},
    );
    return unwrap(data);
  },
};
