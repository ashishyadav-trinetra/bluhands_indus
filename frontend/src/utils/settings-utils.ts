import { WebClientFeatureFlags } from "#/api/option-service/option.types";
import { Settings, SettingsValue } from "#/types/settings";
import { getProviderId } from "#/utils/map-provider";

const extractBasicFormData = (formData: FormData) => {
  const providerDisplay = formData.get("llm-provider-input")?.toString();
  const provider = providerDisplay ? getProviderId(providerDisplay) : undefined;
  const model = formData.get("llm-model-input")?.toString();

  return {
    llmModel: provider && model ? `${provider}/${model}` : undefined,
    llmApiKey: formData.get("llm-api-key-input")?.toString(),
    agent: formData.get("agent")?.toString(),
    language: formData.get("language")?.toString(),
  };
};

/**
 * Parses and validates a max budget per task value.
 * Ensures the value is at least 1 dollar.
 * @param value - The string value to parse
 * @returns The parsed number if valid (>= 1), null otherwise
 */
export const parseMaxBudgetPerTask = (value: string): number | null => {
  if (!value) {
    return null;
  }

  const parsedValue = parseFloat(value);
  return parsedValue && parsedValue >= 1 && Number.isFinite(parsedValue)
    ? parsedValue
    : null;
};

export const extractSettings = (
  formData: FormData,
): Partial<Settings> & Record<string, unknown> => {
  const { llmModel, llmApiKey, agent, language } =
    extractBasicFormData(formData);

  const llm: Record<string, unknown> = {};
  if (llmModel) llm.model = llmModel;
  if (llmApiKey !== undefined) llm.api_key = llmApiKey;

  const agentSettings: Record<string, SettingsValue> = {};
  if (Object.keys(llm).length > 0)
    agentSettings.llm = llm as Record<string, SettingsValue>;
  if (agent) agentSettings.agent = agent;

  return {
    ...(Object.keys(agentSettings).length > 0
      ? { agent_settings_diff: agentSettings }
      : {}),
    ...(language ? { language } : {}),
  };
};

/**
 * Checks if a settings page should be hidden based on feature flags.
 * Used by both the route loader and navigation hook to keep logic in sync.
 *
 * Three user tiers:
 *   1. Admin (admin@trinetralabs.ai) → sees ALL settings tabs
 *   2. Trinetra non-admin (@trinetralabs.ai) → sees NO settings (model locked to Qwen)
 *   3. Normal user (everyone else) → sees only /settings (LLM basic view)
 */
export function isSettingsPageHidden(
  path: string,
  featureFlags: WebClientFeatureFlags | undefined,
  userEmail?: string,
): boolean {
  const emailLower = (userEmail || "").trim().toLowerCase();
  const isAdmin = emailLower === "admin@trinetralabs.ai";
  const isTrinetra = emailLower.endsWith("@trinetralabs.ai");

  // ── Tier 1: Admin sees everything — skip all RBAC checks ──────────────
  if (isAdmin) {
    // Still respect feature-flag toggles below, but no role-based hiding.
  }
  // ── Tier 2: Trinetra non-admin — NO settings at all ───────────────────
  else if (isTrinetra) {
    if (path.startsWith("/settings")) return true;
  }
  // ── Tier 3: Normal user — only /settings (LLM basic view) ─────────────
  else if (emailLower) {
    // Allow exactly /settings (the LLM index route). Hide every other sub-route.
    if (path.startsWith("/settings") && path !== "/settings") return true;
  }

  // ── Feature-flag overrides (apply to all users including admin) ────────
  if (
    featureFlags?.hide_llm_settings &&
    (path === "/settings" || path.startsWith("/settings/org-defaults"))
  )
    return true;
  if (featureFlags?.hide_users_page && path === "/settings/user") return true;
  if (featureFlags?.hide_billing_page && path === "/settings/billing")
    return true;
  if (featureFlags?.hide_integrations_page && path === "/settings/integrations")
    return true;
  return false;
}

/**
 * Find the first available settings page that is not hidden.
 * Returns null if no page is available (shouldn't happen in practice).
 */
export function getFirstAvailablePath(
  isSaas: boolean,
  featureFlags: WebClientFeatureFlags | undefined,
  userEmail?: string,
): string | null {
  const saasFallbackOrder = [
    { path: "/settings/user", hidden: !!featureFlags?.hide_users_page },
    {
      path: "/settings/integrations",
      hidden: !!featureFlags?.hide_integrations_page,
    },
    { path: "/settings/app", hidden: false },
    { path: "/settings", hidden: !!featureFlags?.hide_llm_settings },
    { path: "/settings/billing", hidden: !!featureFlags?.hide_billing_page },
    { path: "/settings/secrets", hidden: false },
    { path: "/settings/api-keys", hidden: false },
    { path: "/settings/mcp", hidden: false },
  ];

  const ossFallbackOrder = [
    { path: "/settings", hidden: !!featureFlags?.hide_llm_settings },
    { path: "/settings/mcp", hidden: false },
    {
      path: "/settings/integrations",
      hidden: !!featureFlags?.hide_integrations_page,
    },
    { path: "/settings/app", hidden: false },
    { path: "/settings/secrets", hidden: false },
  ];

  const fallbackOrder = isSaas ? saasFallbackOrder : ossFallbackOrder;
  // Also pass the fallback paths through isSettingsPageHidden just in case
  const firstAvailable = fallbackOrder.find(
    (item) => !item.hidden && !isSettingsPageHidden(item.path, featureFlags, userEmail),
  );

  return firstAvailable?.path ?? null;
}
