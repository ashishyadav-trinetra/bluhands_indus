import React from "react";
import { useNavigate } from "react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { forgeService } from "#/api/bluhands-service/forge.api";
import { useForgeMe } from "#/hooks/query/use-forge-me";
import type { Industry } from "#/api/bluhands-service/forge.types";

const INDUSTRIES: { id: Industry; label: string; icon: string; description: string }[] = [
  { id: "ecommerce", label: "E-commerce", icon: "🛍️", description: "Online store with products & checkout" },
  { id: "restaurant", label: "Restaurant", icon: "🍽️", description: "Menu, ordering & reservations" },
  { id: "crm", label: "CRM", icon: "👥", description: "Contacts, deals & pipeline" },
  { id: "erp", label: "ERP", icon: "🏭", description: "Operations, inventory & finance" },
  { id: "healthcare", label: "Healthcare", icon: "🏥", description: "Appointments, patients & records" },
];

export default function ForgeSetup() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: me } = useForgeMe();

  const orgId = me?.memberships[0]?.org_id;

  const [selected, setSelected] = React.useState<Industry | null>(null);
  const [displayName, setDisplayName] = React.useState("");

  const { mutate: createTenant, isPending, error } = useMutation({
    mutationFn: () =>
      forgeService.createTenant(orgId!, {
        industry: selected!,
        display_name: displayName.trim() || undefined,
      }),
    onSuccess: (tenant) => {
      queryClient.invalidateQueries({ queryKey: ["forge", "tenants", orgId] });
      navigate("/", { replace: true });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selected || !orgId || isPending) return;
    createTenant();
  };

  return (
    <div className="min-h-screen bg-[#0a0c10] flex items-center justify-center p-6">
      <div className="w-full max-w-[540px]">
        {/* Header */}
        <div className="text-center mb-10">
          <div className="w-14 h-14 rounded-2xl overflow-hidden mx-auto mb-5 shadow-lg shadow-[#3b82f6]/20">
            <img src="/blu-hands-logo.png.png" alt="Blu Hands" className="w-full h-full object-cover" />
          </div>
          <h1 className="text-[28px] font-semibold text-white mb-2">What kind of business are you building?</h1>
          <p className="text-sm text-[#666]">
            BluHands will set up the right backend and build your frontend automatically.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Industry grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {INDUSTRIES.map((ind) => {
              const isSelected = selected === ind.id;
              return (
                <button
                  key={ind.id}
                  type="button"
                  onClick={() => setSelected(ind.id)}
                  className={`flex items-start gap-3 p-4 rounded-xl border text-left transition-all duration-150 cursor-pointer
                    ${isSelected
                      ? "border-[#3b82f6]/70 bg-[#3b82f6]/10"
                      : "border-[#2a2d37] bg-[#111318]/60 hover:border-[#3b82f6]/30 hover:bg-[#1a1c22]"
                    }`}
                >
                  <span className="text-2xl mt-0.5 shrink-0">{ind.icon}</span>
                  <div>
                    <p className={`text-sm font-medium ${isSelected ? "text-[#60a5fa]" : "text-white"}`}>
                      {ind.label}
                    </p>
                    <p className="text-[12px] text-[#666] mt-0.5">{ind.description}</p>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Optional display name */}
          <div>
            <label className="block text-xs text-[#666] mb-1.5" htmlFor="display-name">
              Store name <span className="text-[#444]">(optional)</span>
            </label>
            <input
              id="display-name"
              type="text"
              placeholder="e.g. Artisan Brew Co."
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              maxLength={200}
              className="w-full bg-[#111318] border border-[#2a2d37] focus:border-[#3b82f6]/50 rounded-xl px-4 py-2.5 text-sm text-white placeholder-[#444] outline-none transition-colors"
            />
          </div>

          {error && (
            <p className="text-xs text-red-400">
              {(error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
                ?? "Something went wrong. Please try again."}
            </p>
          )}

          <button
            type="submit"
            disabled={!selected || isPending}
            className="w-full py-3 rounded-xl bg-[#3b82f6] hover:bg-[#2563eb] disabled:opacity-30 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors flex items-center justify-center gap-2"
          >
            {isPending ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Setting up…
              </>
            ) : (
              "Set up my store →"
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
