import React from "react";
import { useNavigate, useParams } from "react-router";
import { useQuery, useMutation } from "@tanstack/react-query";
import { forgeService } from "#/api/bluhands-service/forge.api";
import type { BuildStatus } from "#/api/bluhands-service/forge.types";

// Terminal or completed states where polling can stop.
const TERMINAL: BuildStatus[] = ["live", "failed", "cancelled"];
// States that are still progressing (non-terminal).
const IN_PROGRESS: BuildStatus[] = ["queued", "provisioning", "building", "testing"];

const STATUS_LABEL: Record<BuildStatus, string> = {
  queued: "Queued",
  provisioning: "Provisioning sandbox",
  building: "Building your frontend",
  testing: "Running tests",
  review: "Ready for review",
  live: "Live!",
  updating: "Updating",
  failed: "Build failed",
  cancelled: "Cancelled",
};

const STATUS_COLOUR: Record<BuildStatus, string> = {
  queued: "text-[#888] border-[#2a2d37]",
  provisioning: "text-blue-400 border-blue-400/30",
  building: "text-blue-400 border-blue-400/30",
  testing: "text-yellow-400 border-yellow-400/30",
  review: "text-emerald-400 border-emerald-400/30",
  live: "text-emerald-400 border-emerald-400/30",
  updating: "text-blue-400 border-blue-400/30",
  failed: "text-red-400 border-red-400/30",
  cancelled: "text-[#888] border-[#2a2d37]",
};

// Steps shown in the progress bar, in order.
const STEPS: BuildStatus[] = ["queued", "provisioning", "building", "testing", "review", "live"];

function stepIndex(status: BuildStatus): number {
  const idx = STEPS.indexOf(status);
  return idx === -1 ? 0 : idx;
}

export default function ForgeBuild() {
  const { orgId, tenantId, buildId } = useParams<{
    orgId: string;
    tenantId: string;
    buildId: string;
  }>();
  const navigate = useNavigate();

  const { data: build, error } = useQuery({
    queryKey: ["forge", "build", buildId],
    queryFn: () => forgeService.getBuild(orgId!, tenantId!, buildId!),
    enabled: !!(orgId && tenantId && buildId),
    // Poll every 3 s while the build is in-progress; stop when terminal.
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (!status || TERMINAL.includes(status)) return false;
      return 3000;
    },
  });

  const { mutate: approve, isPending: isApproving } = useMutation({
    mutationFn: () => forgeService.approveBuild(orgId!, tenantId!, buildId!),
  });

  const { mutate: cancel, isPending: isCancelling } = useMutation({
    mutationFn: () => forgeService.cancelBuild(orgId!, tenantId!, buildId!),
    onSuccess: () => navigate("/"),
  });

  if (error) {
    return (
      <div className="min-h-screen bg-[#0a0c10] flex items-center justify-center text-red-400 text-sm">
        Failed to load build. <button type="button" onClick={() => navigate("/")} className="ml-2 underline">Go home</button>
      </div>
    );
  }

  const status = build?.status ?? "queued";
  const currentStep = stepIndex(status);

  return (
    <div className="min-h-screen bg-[#0a0c10] flex flex-col items-center justify-center p-6">
      <div className="w-full max-w-[560px]">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-xl overflow-hidden mx-auto mb-4">
            <img src="/blu-hands-logo.png.png" alt="Blu Hands" className="w-full h-full object-cover" />
          </div>
          <h1 className="text-xl font-semibold text-white mb-1">
            {status === "live" ? "Your store is live!" : "Building your store…"}
          </h1>
          <p className="text-sm text-[#666]">
            {build?.prompt ? `"${build.prompt.slice(0, 80)}${build.prompt.length > 80 ? "…" : ""}"` : ""}
          </p>
        </div>

        {/* Progress steps */}
        <div className="bg-[#111318] border border-[#2a2d37] rounded-2xl p-6 mb-6">
          <div className="flex items-center gap-2 mb-6">
            <span className={`text-xs px-2.5 py-1 rounded-full border font-medium ${STATUS_COLOUR[status]}`}>
              {STATUS_LABEL[status]}
            </span>
            {IN_PROGRESS.includes(status) && (
              <div className="w-3.5 h-3.5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
            )}
          </div>

          {/* Step track */}
          <div className="space-y-3">
            {STEPS.map((step, idx) => {
              const done = idx < currentStep;
              const active = idx === currentStep;
              const upcoming = idx > currentStep;
              return (
                <div key={step} className="flex items-center gap-3">
                  <div
                    className={`w-5 h-5 rounded-full border flex items-center justify-center shrink-0 transition-colors
                      ${done ? "bg-[#3b82f6] border-[#3b82f6]" : active ? "border-[#3b82f6] bg-[#3b82f6]/20" : "border-[#2a2d37] bg-transparent"}`}
                  >
                    {done && (
                      <svg width="8" height="8" fill="none" stroke="white" strokeWidth="2.5">
                        <path d="M1 4l2 2 4-4" />
                      </svg>
                    )}
                    {active && <div className="w-2 h-2 rounded-full bg-[#3b82f6]" />}
                  </div>
                  <span className={`text-sm ${done ? "text-[#9099ac]" : active ? "text-white font-medium" : "text-[#444]"}`}>
                    {STATUS_LABEL[step]}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Error message */}
        {status === "failed" && build?.error && (
          <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 mb-4 text-sm text-red-400">
            {build.error}
          </div>
        )}

        {/* Review actions */}
        {status === "review" && (
          <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-5 mb-4">
            <p className="text-sm text-emerald-300 font-medium mb-1">Build complete — ready to deploy</p>
            <p className="text-xs text-[#666] mb-4">
              Review the preview then approve to go live.
            </p>
            {build?.preview_url && (
              <a
                href={build.preview_url}
                target="_blank"
                rel="noreferrer"
                className="block text-xs text-[#3b82f6] hover:underline mb-4 truncate"
              >
                Preview: {build.preview_url}
              </a>
            )}
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => approve()}
                disabled={isApproving}
                className="flex-1 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-40 text-white text-sm font-medium transition-colors"
              >
                {isApproving ? "Approving…" : "Approve & go live"}
              </button>
              <button
                type="button"
                onClick={() => cancel()}
                disabled={isCancelling}
                className="px-4 py-2.5 rounded-xl border border-[#2a2d37] hover:border-red-500/40 text-[#888] hover:text-red-400 text-sm transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Live state */}
        {status === "live" && build?.prod_url && (
          <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-5 mb-4 text-center">
            <p className="text-sm text-emerald-300 font-medium mb-3">Your store is live</p>
            <a
              href={build.prod_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-white text-sm font-medium transition-colors"
            >
              Open store →
            </a>
          </div>
        )}

        {/* Footer nav */}
        <div className="text-center">
          <button
            type="button"
            onClick={() => navigate("/")}
            className="text-xs text-[#555] hover:text-white transition-colors"
          >
            ← Back to home
          </button>
        </div>
      </div>
    </div>
  );
}
