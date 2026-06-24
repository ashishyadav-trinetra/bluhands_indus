/**
 * UpgradePrompt — modal shown when a 402 UPGRADE_REQUIRED response is received.
 *
 * Usage:
 *   import { useUpgradePrompt, UpgradePromptModal } from "#/components/features/upgrade/upgrade-prompt";
 *
 *   // In a top-level layout:
 *   const { modal, showUpgradePrompt } = useUpgradePrompt();
 *   return <><Outlet />{modal}</>;
 *
 *   // In any API call error handler:
 *   if (err?.response?.status === 402) showUpgradePrompt(err.response.data);
 */
import React from "react";
import { useNavigate } from "react-router";

interface UpgradePayload {
  code: string;
  feature: string;
  current_plan: string;
  required_plan: string;
  message: string;
}

interface UpgradePromptModalProps {
  payload: UpgradePayload | null;
  onClose: () => void;
}

const PLAN_LABEL: Record<string, string> = {
  free: "Free",
  pro: "Pro — $5/mo",
  business: "Business — $50/mo",
  enterprise: "Enterprise",
};

const FEATURE_LABEL: Record<string, string> = {
  max_members: "Team members",
  file_export: "File export",
  priority_queue: "Priority queue",
  sso: "SSO / SAML",
  audit_logs: "Audit logs",
  managed_credits: "Managed AI credits",
};

export function UpgradePromptModal({
  payload,
  onClose,
}: UpgradePromptModalProps) {
  const navigate = useNavigate();

  if (!payload) return null;

  const featureLabel = FEATURE_LABEL[payload.feature] ?? payload.feature;
  const requiredLabel =
    PLAN_LABEL[payload.required_plan] ?? payload.required_plan;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl border border-[#2a2d37] bg-[#111318] p-8 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Icon */}
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-[#1e1040]">
          <svg
            className="h-6 w-6 text-[#7C3AED]"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M13 10V3L4 14h7v7l9-11h-7z"
            />
          </svg>
        </div>

        <h2 className="mb-2 text-xl font-bold text-white">Upgrade required</h2>
        <p className="mb-1 text-sm text-[#94a3b8]">
          <strong className="text-white">{featureLabel}</strong> is not
          available on your current plan.
        </p>
        <p className="mb-6 text-sm text-[#64748b]">
          Upgrade to <strong className="text-[#a78bfa]">{requiredLabel}</strong>{" "}
          to unlock this feature.
        </p>

        {/* Plan comparison strip */}
        <div className="mb-6 rounded-xl border border-[#1e293b] bg-[#0f1117] p-4">
          <div className="flex items-center justify-between text-sm">
            <div>
              <p className="text-[#64748b]">Current plan</p>
              <p className="font-semibold text-white capitalize">
                {payload.current_plan}
              </p>
            </div>
            <svg
              className="h-4 w-4 text-[#475569]"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 5l7 7-7 7"
              />
            </svg>
            <div className="text-right">
              <p className="text-[#64748b]">Needed</p>
              <p className="font-semibold text-[#a78bfa] capitalize">
                {payload.required_plan}
              </p>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <button
            type="button"
            onClick={() => {
              onClose();
              navigate("/pricing");
            }}
            className="flex-1 rounded-xl bg-[#7C3AED] py-2.5 text-sm font-semibold text-white hover:bg-[#6d28d9]"
          >
            View plans
          </button>
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-[#2a2d37] px-4 py-2.5 text-sm text-[#64748b] hover:text-white"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * Hook that manages upgrade prompt state.
 * Add <UpgradePromptModal> to your layout and call showUpgradePrompt() from any error handler.
 */
export function useUpgradePrompt() {
  const [payload, setPayload] = React.useState<UpgradePayload | null>(null);

  const showUpgradePrompt = React.useCallback((data: unknown) => {
    const p = data as UpgradePayload;
    if (p?.code === "UPGRADE_REQUIRED") {
      setPayload(p);
    }
  }, []);

  const modal = (
    <UpgradePromptModal payload={payload} onClose={() => setPayload(null)} />
  );

  return { modal, showUpgradePrompt };
}

/**
 * Axios response interceptor helper.
 * Call this once in your app root to automatically show the upgrade modal on 402 errors.
 *
 * Example:
 *   install402Interceptor(openHands, showUpgradePrompt);
 */
export function install402Interceptor(
  axiosInstance: { interceptors: { response: { use: Function } } },
  showUpgradePrompt: (data: unknown) => void,
) {
  axiosInstance.interceptors.response.use(
    (r: unknown) => r,
    (err: { response?: { status: number; data: unknown } }) => {
      if (err?.response?.status === 402) {
        showUpgradePrompt(err.response.data);
      }
      return Promise.reject(err);
    },
  );
}
