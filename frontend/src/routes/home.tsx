import React from "react";
import toast from "react-hot-toast";
import { PrefetchPageLinks, useNavigate } from "react-router";
import { useSettings } from "#/hooks/query/use-settings";
import { useGitUser } from "#/hooks/query/use-git-user";
import { usePaginatedConversations } from "#/hooks/query/use-paginated-conversations";
import { useCreateConversation } from "#/hooks/mutation/use-create-conversation";
import { useAppMode } from "#/hooks/use-app-mode";
import { HomepageCTA } from "#/components/features/home/homepage-cta";
import { isCTADismissed } from "#/utils/local-storage";
import { useForgeMe } from "#/hooks/query/use-forge-me";
import { useForgeTenants } from "#/hooks/query/use-forge-tenant";
// useStartBuild removed — all builds now go through OpenHands conversations
import { useDeleteConversation } from "#/hooks/mutation/use-delete-conversation";
// GitHub is handled natively by the OpenHands app-server: connect a token in
// Settings → Integrations (POST /api/v1/secrets/provider-tokens), and the agent
// clones/pushes/opens PRs in the conversation. The old Nango/forge GitHub path
// was removed.

// ─── Smart LLM-powered clarification overlay ──────────────────────────────────
interface AgentQuestion {
  id: string;
  text: string;
  kind: "single" | "multi" | "text";
  options: string[];
  allow_other: boolean;
  help: string;
}

interface ClarifyOverlayProps {
  prompt: string;
  initialQuestions: AgentQuestion[];
  onConfirm: (enrichedPrompt: string) => void;
  onBack: () => void;
  isPending: boolean;
}

function ClarifyOverlay({ prompt, initialQuestions, onConfirm, onBack, isPending }: ClarifyOverlayProps) {
  // Questions are pre-fetched by the caller (the overlay only opens when the
  // agent actually has questions — otherwise we build immediately, no dialog).
  const [questions] = React.useState<AgentQuestion[]>(initialQuestions);
  const [answers, setAnswers] = React.useState<Record<string, string | string[]>>({});
  const [activeQ, setActiveQ] = React.useState(0);
  const [enhancing, setEnhancing] = React.useState(false);

  const pickSingle = (qId: string, option: string) => {
    setAnswers((prev) => ({ ...prev, [qId]: option }));
    if (activeQ < questions.length - 1) {
      setTimeout(() => setActiveQ((a) => a + 1), 220);
    }
  };

  const toggleMulti = (qId: string, option: string) => {
    setAnswers((prev) => {
      const current = (prev[qId] as string[]) || [];
      const next = current.includes(option)
        ? current.filter((o) => o !== option)
        : [...current, option];
      return { ...prev, [qId]: next };
    });
  };

  const handleConfirm = async () => {
    setEnhancing(true);
    try {
      const { forgeClient } = await import("#/api/bluhands-service/forge-axios");
      const formattedAnswers = questions.map((q) => {
        const a = answers[q.id];
        return {
          question_id: q.id,
          selected: Array.isArray(a) ? a : (typeof a === "string" && q.kind !== "text" ? [a] : []),
          text: q.kind === "text" && typeof a === "string" ? a : "",
        };
      });
      const r = await forgeClient.post<{ enhanced_prompt: string }>("/api/v1/agent/enhance", {
        prompt,
        clarifications: formattedAnswers,
      });
      onConfirm(r.data?.enhanced_prompt || prompt);
    } catch {
      // Fallback: use raw prompt if enhance fails
      onConfirm(prompt);
    } finally {
      setEnhancing(false);
    }
  };

  const busy = isPending || enhancing;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onBack} />
      <div
        className="relative w-full max-w-[560px] bg-[#0d0f14] border border-[#2a2d37] rounded-2xl shadow-2xl overflow-hidden"
        style={{ boxShadow: "0 0 60px rgba(59,130,246,0.12)" }}
      >
        {/* Header */}
        <div className="px-6 pt-6 pb-4 border-b border-[#1e2028]">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs text-[#3b82f6] font-medium uppercase tracking-wider mb-1">Quick questions</p>
              <h2 className="text-white font-semibold text-base leading-snug">
                Let&apos;s tailor this for you
              </h2>
            </div>
            <button type="button" onClick={onBack} className="text-[#555] hover:text-white transition-colors mt-0.5 shrink-0" aria-label="Back">
              <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 8h8M4 8l3-3M4 8l3 3" /></svg>
            </button>
          </div>
          <p className="mt-3 text-xs text-[#666] bg-[#111318] rounded-lg px-3 py-2 border border-[#1e2028] line-clamp-2">
            &ldquo;{prompt}&rdquo;
          </p>
        </div>

        {/* Body */}
        <div className="px-6 py-5 space-y-5 max-h-[60vh] overflow-y-auto custom-scrollbar">
          {questions.map((q, qi) => {
              // All questions are reachable at once — sequential gating used to
              // trap text questions (typing didn't advance the unlock), which
              // left later questions greyed out and "Start building" disabled.
              const isActive = !busy;
              const ans = answers[q.id];
              const answered = q.kind === "text"
                ? typeof ans === "string" && ans.trim().length > 0
                : q.kind === "multi"
                  ? Array.isArray(ans) && ans.length > 0
                  : typeof ans === "string" && ans.length > 0;

              return (
                <div key={q.id} className="transition-all duration-300" style={{ opacity: isActive ? 1 : 0.35 }}>
                  <p className="text-[13px] font-medium text-[#c8cdd6] mb-2.5 flex items-center gap-2">
                    {answered ? (
                      <span className="w-4 h-4 rounded-full bg-[#3b82f6] flex items-center justify-center shrink-0">
                        <svg width="8" height="8" fill="none" stroke="white" strokeWidth="2.5"><path d="M1 4l2 2 4-4" /></svg>
                      </span>
                    ) : (
                      <span className="w-4 h-4 rounded-full border border-[#3b82f6]/40 flex items-center justify-center shrink-0 text-[10px] text-[#3b82f6]">{qi + 1}</span>
                    )}
                    {q.text}
                  </p>
                  {q.help && <p className="text-[11px] text-[#555] mb-2 ml-6">{q.help}</p>}

                  {q.kind === "text" ? (
                    <input
                      type="text"
                      disabled={!isActive || busy}
                      value={typeof ans === "string" ? ans : ""}
                      onChange={(e) => setAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
                      onFocus={() => setActiveQ(qi)}
                      placeholder="Type your answer…"
                      className="w-full bg-[#111318] border border-[#2a2d37] rounded-lg px-3 py-2 text-[12px] text-white placeholder-[#555] outline-none focus:border-[#3b82f6]/50"
                    />
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {q.options.map((opt) => {
                        const selected = q.kind === "multi"
                          ? Array.isArray(ans) && (ans as string[]).includes(opt)
                          : ans === opt;
                        return (
                          <button
                            key={opt}
                            type="button"
                            disabled={!isActive || busy}
                            onClick={() => q.kind === "multi" ? toggleMulti(q.id, opt) : pickSingle(q.id, opt)}
                            className={`text-[12px] px-3 py-1.5 rounded-lg border transition-all duration-150 cursor-pointer
                              ${selected ? "bg-[#3b82f6]/15 border-[#3b82f6]/60 text-[#60a5fa] font-medium" : "bg-[#111318] border-[#2a2d37] text-[#9099ac] hover:border-[#3b82f6]/40 hover:text-white"}
                              disabled:cursor-not-allowed disabled:opacity-50`}
                          >
                            {opt}
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
        </div>

        {/* GitHub — native OpenHands integration. Connect a token once in
            Settings → Integrations; then just ask the agent to clone/push/PR
            during the build (it uses your connected token in the sandbox). */}
        <div className="px-6 py-4 border-t border-[#1e2028]">
          <p className="text-[11px] text-[#3b82f6] font-medium uppercase tracking-wider mb-2">
            GitHub (optional)
          </p>
          <a href="/settings/integrations" className="text-[12px] text-[#3b82f6] hover:underline">
            Connect GitHub in Settings → Integrations →
          </a>
          <p className="text-[11px] text-[#3b4250] mt-1">
            Once connected, ask the agent to clone a repo, push your build, or open a PR.
          </p>
        </div>

        {/* Footer */}
        <div className="px-6 pb-6 pt-4 border-t border-[#1e2028] flex items-center justify-between gap-3">
          <button type="button" onClick={onBack} className="text-[13px] text-[#666] hover:text-white transition-colors">
            ← Edit prompt
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={handleConfirm}
            className="flex items-center gap-2 px-5 py-2 rounded-xl bg-[#3b82f6] hover:bg-[#2563eb] disabled:opacity-30 disabled:cursor-not-allowed text-white text-[13px] font-medium transition-colors"
          >
            {busy ? (
              <><div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />Building…</>
            ) : (
              <>Start building <svg width="13" height="13" fill="none" stroke="white" strokeWidth="2.5"><path d="M2 6.5h9M8 3l3 3.5-3 3.5" /></svg></>
            )}
          </button>
        </div>

        {/* Progress dots */}
        {questions.length > 0 && (
          <div className="flex justify-center gap-1.5 pb-4">
            {questions.map((q, qi) => (
              <div key={q.id} className={`h-1 rounded-full transition-all duration-300 ${answers[q.id] !== undefined ? "w-4 bg-[#3b82f6]" : qi === activeQ ? "w-2 bg-[#3b82f6]/50" : "w-1.5 bg-[#2a2d37]"}`} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

<PrefetchPageLinks page="/conversations/:conversationId" />;

const STARTER_PROMPTS = [
  {
    icon: "🚀",
    title: "Landing page",
    prompt:
      "Create a modern landing page with a hero section, features grid, testimonials, and a CTA. Use React with Tailwind CSS. Make it responsive. Use port 8011 and bind to 0.0.0.0 (not localhost) for the server so it is accessible externally.",
  },
  {
    icon: "🛍️",
    title: "E-commerce store",
    prompt:
      "Build an e-commerce store with a product catalog, shopping cart, and checkout page. Use Node.js with Express and Tailwind CSS. No payment processing yet. Use port 8011 and bind to 0.0.0.0 (not localhost) for the server so it is accessible externally.",
  },
  {
    icon: "📊",
    title: "Dashboard",
    prompt:
      "Create an analytics dashboard with charts, stat cards, and a sidebar navigation. Use React with Tailwind CSS and Recharts for the charts. Use port 8011 and bind to 0.0.0.0 (not localhost) for the server so it is accessible externally.",
  },
  {
    icon: "⚡",
    title: "REST API",
    prompt:
      "Build a REST API with Express.js and a SQLite database. Include user CRUD endpoints, authentication middleware, and proper error handling. Use port 8011 and bind to 0.0.0.0 (not localhost) for the server so it is accessible externally.",
  },
  {
    icon: "✨",
    title: "Portfolio site",
    prompt:
      "Build a personal portfolio website with an about section, project showcase, skills, and contact form. Use a clean modern design with Tailwind CSS. Use port 8011 and bind to 0.0.0.0 (not localhost) for the server so it is accessible externally.",
  },
  {
    icon: "🏗️",
    title: "Full-stack app",
    prompt:
      "Build a full-stack todo app with a React frontend, Express backend, and a SQLite database. Include user authentication, CRUD operations. Use port 8011 and bind to 0.0.0.0 (not localhost) for the server so it is accessible externally.",
  },
  {
    icon: "💬",
    title: "Chat app",
    prompt:
      "Build a real-time chat application with WebSocket support, user nicknames, message history, and a clean modern UI. Use Node.js with Express and Socket.io. Use port 8011 and bind to 0.0.0.0 (not localhost) for the server so it is accessible externally.",
  },
  {
    icon: "📝",
    title: "Blog platform",
    prompt:
      "Build a blog platform with markdown support, post listing, individual post pages, and a clean reading experience. Use Node.js with Express and Tailwind CSS. Use port 8011 and bind to 0.0.0.0 (not localhost) for the server so it is accessible externally.",
  },
];

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

function HomeScreen() {
  const navigate = useNavigate();
  const { isEnterpriseCloud } = useAppMode();
  const { data: settings } = useSettings();
  const user = useGitUser();
  const { data: conversationData } = usePaginatedConversations();
  const { mutate: createConversation, isPending: isConversationPending } =
    useCreateConversation();

  // ── Forge (BluHands control-plane) ────────────────────────────────────────
  const { data: forgeMe } = useForgeMe();
  const forgeOrgId = forgeMe?.memberships[0]?.org_id;
  const { data: forgeTenants } = useForgeTenants(forgeOrgId);
  const forgeTenant = forgeTenants?.[0] ?? null; // kept for industry-nudge hidden ref
  const { mutate: deleteConversation } = useDeleteConversation();

  const isPending = isConversationPending;

  const conversations =
    conversationData?.pages.flatMap((page) => page.items) ?? [];
  const recentConversations = conversations.slice(0, 6);

  const [shouldShowCTA, setShouldShowCTA] = React.useState(
    () => !isCTADismissed("homepage"),
  );

  const [promptValue, setPromptValue] = React.useState("");
  const [attachedImages, setAttachedImages] = React.useState<File[]>([]);
  const [showModelMenu, setShowModelMenu] = React.useState(false);
  const [clarify, setClarify] = React.useState<{ prompt: string; questions: AgentQuestion[] } | null>(null);
  const [checking, setChecking] = React.useState(false);
  const [showUpgrade, setShowUpgrade] = React.useState(false);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const uiBusy = isPending || checking;

  // Prefer the authenticated user's real identity (forge/Supabase) over the
  // per-user OpenHands git name, which is empty for fresh users.
  const userName =
    forgeMe?.full_name ||
    forgeMe?.display_name ||
    settings?.git_user_name ||
    user.data?.login ||
    forgeMe?.email?.split("@")[0] ||
    "there";
  const firstName = userName.split(" ")[0];

  // Extract current model display name
  const currentModel = settings?.llm_model || "gemini-2.0-flash";
  const modelShortName =
    currentModel.split("/").pop()?.split(":")[0] || currentModel;

  const handleImageAttach = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { files } = e.target;
    if (files) {
      setAttachedImages((prev) => [...prev, ...Array.from(files)]);
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const removeImage = (index: number) => {
    setAttachedImages((prev) => prev.filter((_, i) => i !== index));
  };

  // Called with the final (possibly enriched) prompt.
  // Always opens an OpenHands conversation so the user gets the live agent view
  // (VSCode, terminal, App/Changes/Code tabs). The enriched prompt makes the
  // agent work autonomously — no back-and-forth needed.
  const handleCreateWithPrompt = (prompt: string) => {
    if (isPending) return;
    createConversation(
      { query: prompt },
      {
        onSuccess: (data) => navigate(`/conversations/${data.conversation_id}`),
        onError: () => toast.error("Couldn't start the build. Please try again."),
      },
    );
  };

  // The smart entry point: ask the agent if it needs anything. If it returns 0
  // questions (the common case), build IMMEDIATELY — no dialog. Only when the
  // agent has real questions do we pop the MCQ/free-text overlay. Any error →
  // just build.
  const beginBuild = async (prompt: string) => {
    const trimmed = prompt.trim();
    if (!trimmed || uiBusy) return;
    setChecking(true);
    try {
      const { forgeClient } = await import("#/api/bluhands-service/forge-axios");
      const r = await forgeClient.post<{ questions: AgentQuestion[] }>(
        "/api/v1/agent/clarify",
        { prompt: trimmed },
      );
      const qs = r.data?.questions ?? [];
      if (qs.length === 0) {
        handleCreateWithPrompt(trimmed);
      } else {
        setClarify({ prompt: trimmed, questions: qs });
      }
    } catch {
      handleCreateWithPrompt(trimmed); // never block building on a clarify hiccup
    } finally {
      setChecking(false);
    }
  };

  const handleStarterClick = (prompt: string) => {
    void beginBuild(prompt);
  };

  const handlePromptSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    void beginBuild(promptValue);
  };

  return (
    <div
      data-testid="home-screen"
      className="h-full flex flex-col overflow-y-auto custom-scrollbar-always relative"
    >
      {/* Gradient backdrop */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: `
            radial-gradient(ellipse 100% 80% at 50% -20%, rgba(59, 130, 246, 0.35) 0%, transparent 50%),
            radial-gradient(ellipse 70% 60% at 90% 15%, rgba(168, 85, 247, 0.25) 0%, transparent 50%),
            radial-gradient(ellipse 80% 60% at 10% 60%, rgba(59, 130, 246, 0.18) 0%, transparent 50%),
            radial-gradient(ellipse 60% 50% at 70% 95%, rgba(236, 72, 153, 0.20) 0%, transparent 50%)
          `,
        }}
      />

      {/* Content — centered vertically with prompt as hero */}
      <div className="relative z-10 flex flex-col items-center w-full max-w-[720px] mx-auto px-6">
        {/* Spacer to push content to ~40% from top */}
        <div className="h-[20vh]" />

        {/* Logo */}
        <div className="w-14 h-14 rounded-2xl overflow-hidden mb-6 shadow-lg shadow-[#3b82f6]/20">
          <img
            src="/blu-hands-logo.png.png"
            alt="Blu Hands"
            className="w-full h-full object-cover"
          />
        </div>

        {/* Greeting */}
        <h1 className="text-[32px] font-semibold text-white mb-2 text-center">
          Let&apos;s build something,{" "}
          <span className="bg-gradient-to-r from-[#3b82f6] to-[#a855f7] bg-clip-text text-transparent">
            {firstName}
          </span>
        </h1>
        <p className="text-sm text-[#666] mb-8 text-center">
          Describe your project or pick a starter below
        </p>

        {/* Industry setup nudge — hidden for now */}
        {false && forgeOrgId && forgeTenants?.length === 0 && (
          <button
            type="button"
            onClick={() => navigate("/forge/setup")}
            className="w-full mb-5 flex items-center justify-between px-5 py-3.5 rounded-xl border border-[#3b82f6]/30 bg-[#3b82f6]/8 hover:bg-[#3b82f6]/12 transition-colors text-left"
          >
            <div>
              <p className="text-sm font-medium text-white">Set up your industry</p>
              <p className="text-xs text-[#666] mt-0.5">
                Pick your industry so BluHands can wire the right backend for you.
              </p>
            </div>
            <svg width="14" height="14" fill="none" stroke="#3b82f6" strokeWidth="2.5" className="shrink-0 ml-4">
              <path d="M2 7h10M8 3l4 4-4 4" />
            </svg>
          </button>
        )}

        {/* Prompt bar — the hero element */}
        <form onSubmit={handlePromptSubmit} className="w-full mb-8">
          <div className="bg-[#111318]/80 border border-[#2a2d37] rounded-2xl focus-within:border-[#3b82f6]/40 transition-colors">
            {/* Image previews */}
            {attachedImages.length > 0 && (
              <div className="flex gap-2 px-4 pt-3 flex-wrap">
                {attachedImages.map((img, i) => (
                  <div key={i} className="relative group">
                    <img
                      src={URL.createObjectURL(img)}
                      alt="attached"
                      className="w-16 h-16 rounded-lg object-cover border border-[#2a2d37]"
                    />
                    <button
                      type="button"
                      onClick={() => removeImage(i)}
                      className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-[#333] hover:bg-red-500 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <svg width="8" height="8" stroke="white" strokeWidth="2">
                        <path d="M1 1l6 6M7 1l-6 6" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Input row */}
            <div className="flex items-center px-5 py-3">
              <input
                type="text"
                placeholder="Ask Blu Hands to build something..."
                value={promptValue}
                onChange={(e) => setPromptValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && promptValue.trim() && !uiBusy) {
                    e.preventDefault();
                    void beginBuild(promptValue);
                  }
                }}
                className="flex-1 bg-transparent text-sm text-white placeholder-[#555] outline-none"
                disabled={uiBusy}
                autoFocus
              />
              <button
                type="submit"
                disabled={uiBusy || !promptValue.trim()}
                className="ml-3 w-9 h-9 rounded-full bg-[#3b82f6] hover:bg-[#2563eb] disabled:opacity-30 disabled:cursor-not-allowed flex items-center justify-center transition-colors shrink-0"
              >
                {uiBusy ? (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <svg
                    width="14"
                    height="14"
                    fill="none"
                    stroke="white"
                    strokeWidth="2.5"
                  >
                    <path d="M2 7h10M8 3l4 4-4 4" />
                  </svg>
                )}
              </button>
            </div>

            {/* Bottom toolbar: + attach, model selector */}
            <div className="flex items-center justify-between px-4 pb-3 pt-0">
              {/* Attach image */}
              <div className="flex items-center gap-2">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={handleImageAttach}
                  className="hidden"
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="w-7 h-7 rounded-lg border border-[#2a2d37] hover:border-[#3b82f6]/40 hover:bg-[#1e2028] flex items-center justify-center text-[#666] hover:text-white transition-all"
                  title="Attach image"
                >
                  <svg
                    width="14"
                    height="14"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.5"
                  >
                    <path d="M7 3v8M3 7h8" />
                  </svg>
                </button>
                {attachedImages.length > 0 && (
                  <span className="text-[11px] text-[#555]">
                    {attachedImages.length} image
                    {attachedImages.length > 1 ? "s" : ""}
                  </span>
                )}
              </div>

              {/* Model selector */}
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setShowModelMenu(!showModelMenu)}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-[#2a2d37] hover:border-[#3b82f6]/40 text-[11px] text-[#888] hover:text-white transition-all"
                >
                  <span className="truncate max-w-[140px]">
                    {modelShortName}
                  </span>
                  <svg
                    width="10"
                    height="10"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.5"
                  >
                    <path d="M2.5 4L5 6.5 7.5 4" />
                  </svg>
                </button>

                {showModelMenu && (
                  <>
                    <div
                      className="fixed inset-0 z-40"
                      onClick={() => setShowModelMenu(false)}
                    />
                    <div className="absolute bottom-full right-0 mb-2 w-[220px] bg-[#111318] border border-[#2a2d37] rounded-xl p-2 z-50 shadow-xl">
                      <p className="text-[10px] text-[#555] uppercase tracking-wider px-2 py-1 mb-1">
                        Switch model
                      </p>
                      {[
                        "google/gemini-2.0-flash-001:free",
                        "qwen/qwen3-235b-a22b:free",
                        "meta-llama/llama-4-maverick:free",
                        "openai/gpt-4o",
                        "anthropic/claude-sonnet-4-5-20250929",
                      ].map((model) => {
                        const name =
                          model.split("/").pop()?.split(":")[0] || model;
                        const isFree = model.includes(":free");
                        const isActive = currentModel === model;
                        return (
                          <button
                            key={model}
                            type="button"
                            onClick={() => {
                              // Navigate to settings to change model
                              navigate("/settings");
                              setShowModelMenu(false);
                            }}
                            className={`w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-xs text-left transition-colors ${
                              isActive
                                ? "bg-[#3b82f6]/15 text-[#60a5fa]"
                                : "text-[#9099ac] hover:bg-[#1e2028] hover:text-white"
                            }`}
                          >
                            <span className="truncate">{name}</span>
                            {isFree && (
                              <span className="text-[9px] bg-emerald-500/15 text-emerald-400 px-1.5 py-0.5 rounded shrink-0 ml-2">
                                free
                              </span>
                            )}
                          </button>
                        );
                      })}
                      <div className="border-t border-[#2a2d37] mt-1 pt-1">
                        <button
                          type="button"
                          onClick={() => {
                            navigate("/settings");
                            setShowModelMenu(false);
                          }}
                          className="w-full px-2.5 py-2 rounded-lg text-xs text-[#3b82f6] hover:bg-[#1e2028] text-left transition-colors"
                        >
                          All models & API keys →
                        </button>
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        </form>

        {/* Starters — horizontal scroll, single row */}
        <div className="w-full mb-4">
          <div
            className="flex gap-2.5 overflow-x-auto pb-2 custom-scrollbar"
            style={{ scrollbarWidth: "none" }}
          >
            {STARTER_PROMPTS.map((starter) => (
              <button
                key={starter.title}
                type="button"
                onClick={() => handleStarterClick(starter.prompt)}
                disabled={uiBusy}
                className="group shrink-0 border border-[#2a2d37]/60 rounded-xl bg-[#111318]/50 hover:bg-[#1a1c22]/80 hover:border-[#3b82f6]/30 disabled:opacity-50 flex items-center gap-2.5 px-4 py-3 text-left transition-all duration-200 cursor-pointer"
              >
                <span className="text-lg">{starter.icon}</span>
                <span className="text-[13px] font-medium text-[#9099ac] group-hover:text-white whitespace-nowrap transition-colors">
                  {starter.title}
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Spacer — panel appears below the fold */}
        <div className="h-[28vh]" />

        {/* Projects panel — Lovable-style tabbed section */}
        <div className="w-full pb-12">
          <div className="rounded-2xl border border-white/[0.06] bg-[#0f1014] overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between px-4 pt-3.5 pb-2.5 border-b border-white/[0.04]">
              <span className="text-[12px] font-medium text-[#e2e8f0]">My projects</span>
              {recentConversations.length > 0 && (
                <button
                  type="button"
                  onClick={() => navigate("/conversations")}
                  className="flex items-center gap-1 text-[11px] text-[#3b4250] hover:text-[#64748b] transition-colors"
                >
                  Browse all
                  <svg width="10" height="10" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M2 5h6M6 2l3 3-3 3" />
                  </svg>
                </button>
              )}
            </div>

            {/* Content */}
            <div className="p-4">
              {recentConversations.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-10 gap-2">
                  <svg width="32" height="32" fill="none" viewBox="0 0 32 32" className="opacity-[0.08]">
                    <rect x="4" y="4" width="24" height="24" rx="4" stroke="#9ca3af" strokeWidth="1.5" />
                    <path d="M10 16h12M16 10v12" stroke="#9ca3af" strokeWidth="1.5" strokeLinecap="round" />
                  </svg>
                  <p className="text-[12px] text-[#2d3340]">No projects yet — start building above</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {recentConversations.map((conversation) => (
                    <div
                      key={conversation.id}
                      className="group relative rounded-xl border border-white/[0.05] bg-[#111318] hover:border-white/[0.09] hover:bg-[#141720] transition-all duration-150 overflow-hidden"
                    >
                      {/* Card body — navigates to conversation */}
                      <button
                        type="button"
                        onClick={() => navigate(`/conversations/${conversation.id}`)}
                        className="w-full text-left"
                      >
                        <div className="aspect-[16/9] bg-[#0c0e13] flex items-center justify-center border-b border-white/[0.04]">
                          <svg width="28" height="28" fill="none" viewBox="0 0 28 28" className="opacity-[0.12]">
                            <rect x="3" y="5" width="22" height="15" rx="2" stroke="#9ca3af" strokeWidth="1.4" />
                            <path d="M9 23h10" stroke="#9ca3af" strokeWidth="1.4" strokeLinecap="round" />
                            <path d="M14 20v3" stroke="#9ca3af" strokeWidth="1.4" strokeLinecap="round" />
                          </svg>
                        </div>
                        <div className="px-3 py-2.5 pr-8">
                          <p className="text-[12px] font-medium text-[#cbd5e1] group-hover:text-white truncate transition-colors">
                            {conversation.title || "Untitled"}
                          </p>
                          <p className="text-[10px] text-[#2d3340] mt-0.5">
                            {conversation.updated_at ? formatRelativeTime(conversation.updated_at) : ""}
                          </p>
                        </div>
                      </button>

                      {/* Delete button — appears on hover */}
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteConversation({ conversationId: conversation.id });
                        }}
                        className="absolute top-2 right-2 w-6 h-6 rounded-md bg-[#1a1c22] border border-white/[0.06] flex items-center justify-center text-[#444] hover:text-red-400 hover:border-red-500/30 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-all duration-150"
                        title="Delete project"
                        aria-label="Delete project"
                      >
                        <svg width="11" height="11" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
                          <path d="M2 2l7 7M9 2l-7 7" />
                        </svg>
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {isEnterpriseCloud && shouldShowCTA && (
        <div className="fixed bottom-4 right-8 z-50 md:bottom-6 md:right-12">
          <HomepageCTA setShouldShowCTA={setShouldShowCTA} />
        </div>
      )}

      {/* Clarification overlay — only shown when the agent actually has questions */}
      {clarify && (
        <ClarifyOverlay
          prompt={clarify.prompt}
          initialQuestions={clarify.questions}
          isPending={isPending}
          onBack={() => setClarify(null)}
          onConfirm={(enriched) => {
            setClarify(null);
            handleCreateWithPrompt(enriched);
          }}
        />
      )}

      {/* Upgrade popup — shown when a non-Pro user tries to build (402) */}
      {showUpgrade && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-black/70 backdrop-blur-sm"
            onClick={() => setShowUpgrade(false)}
          />
          <div className="relative w-full max-w-[420px] bg-[#0d0f14] border border-[#2a2d37] rounded-2xl shadow-2xl overflow-hidden p-7 text-center">
            <div className="w-12 h-12 mx-auto mb-4 rounded-xl bg-gradient-to-br from-[#3b82f6] to-[#a855f7] flex items-center justify-center">
              <svg width="22" height="22" fill="none" stroke="white" strokeWidth="2">
                <path d="M11 2l2.5 5 5.5.8-4 3.9.9 5.5L11 20.6 6.1 23l.9-5.5-4-3.9 5.5-.8z" />
              </svg>
            </div>
            <h2 className="text-white font-semibold text-lg mb-1">Upgrade to build</h2>
            <p className="text-sm text-[#9099ac] mb-6">
              Building apps with the AI agent is a Pro feature. Upgrade your plan to
              start building, or ask an admin to enable access for your account.
            </p>
            <div className="flex flex-col gap-2">
              <button
                type="button"
                onClick={() => {
                  setShowUpgrade(false);
                  navigate("/settings/billing");
                }}
                className="w-full py-2.5 rounded-xl bg-[#3b82f6] hover:bg-[#2563eb] text-white text-sm font-medium transition-colors"
              >
                Upgrade to Pro
              </button>
              <button
                type="button"
                onClick={() => setShowUpgrade(false)}
                className="w-full py-2 text-[13px] text-[#666] hover:text-white transition-colors"
              >
                Maybe later
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default HomeScreen;
