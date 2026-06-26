"use client";

import { AlertTriangle, ChevronDown, ChevronUp, RefreshCcw, LifeBuoy } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { Button } from "./button";

// --- Error categorisation ------------------------------------------------

export type ErrorCategory =
  | "credits"
  | "timeout"
  | "ai_agent"
  | "compile"
  | "infra"
  | "auth"
  | "network"
  | "unknown";

const CATEGORY_META: Record<
  ErrorCategory,
  { title: string; explanation: string; badge: string; canRetry: boolean }
> = {
  credits: {
    title: "AI credits exhausted",
    explanation:
      "The AI ran out of processing credits mid-build. This is a platform issue — contact support and we'll retry your build at no extra cost.",
    badge: "Platform issue",
    canRetry: false,
  },
  timeout: {
    title: "Build timed out",
    explanation:
      "The build sandbox took too long to respond. This is usually transient — retrying almost always succeeds.",
    badge: "Transient",
    canRetry: true,
  },
  ai_agent: {
    title: "AI agent crashed",
    explanation:
      "The AI agent hit an unexpected error while generating your storefront. A retry with fresh context usually fixes it.",
    badge: "AI error",
    canRetry: true,
  },
  compile: {
    title: "Generated code didn't compile",
    explanation:
      "The AI wrote code that failed TypeScript or build checks. This happens occasionally — retrying usually produces working code.",
    badge: "Build error",
    canRetry: true,
  },
  infra: {
    title: "Internal platform error",
    explanation:
      "An infrastructure error interrupted your build (event loop, database connection, etc.). Our team has been notified. Please retry.",
    badge: "Infrastructure",
    canRetry: true,
  },
  auth: {
    title: "Authentication error",
    explanation:
      "Your session may have expired or your account lacks the required permissions. Try signing out and back in.",
    badge: "Auth",
    canRetry: false,
  },
  network: {
    title: "Network error",
    explanation:
      "Could not reach the server. Check your connection and try again.",
    badge: "Network",
    canRetry: true,
  },
  unknown: {
    title: "Something went wrong",
    explanation:
      "An unexpected error occurred. Please retry or contact support if it keeps happening.",
    badge: "Unknown",
    canRetry: true,
  },
};

/** Map a raw error string → a category. */
export function categoriseError(raw: string | null | undefined): ErrorCategory {
  if (!raw) return "unknown";
  const s = raw.toLowerCase();
  if (/credits|402|payment required|afford|openrouter/.test(s)) return "credits";
  if (/readtimeout|soft time limit|timedout|timed.?out|deadline/.test(s)) return "timeout";
  if (/conversationrunerror|openhands|llm|litellm|apierror/.test(s)) return "ai_agent";
  if (/type error|build error|exit code: 1|next.js build|compilation|ts\(/.test(s)) return "compile";
  if (/different loop|event loop|runtimeerror|greenlet|asyncpg/.test(s)) return "infra";
  if (/401|403|unauthorized|forbidden|jwt|token/.test(s)) return "auth";
  if (/econnrefused|network|fetch failed|connection refused/.test(s)) return "network";
  return "unknown";
}

// --- Component ---------------------------------------------------------------

interface ErrorCardProps {
  /** Raw error string from the server or caught exception. */
  error: string | null | undefined;
  /** Override the auto-detected category. */
  category?: ErrorCategory;
  /** Title shown above the explanation. Falls back to category default. */
  title?: string;
  /** Extra explanation text appended after the category explanation. */
  detail?: string;
  /** Callback for the "Retry" button. If omitted, no retry button is shown. */
  onRetry?: () => void;
  retryLabel?: string;
  /** Whether the retry action is loading. */
  retrying?: boolean;
  className?: string;
}

export function ErrorCard({
  error,
  category: categoryProp,
  title: titleProp,
  detail,
  onRetry,
  retryLabel = "Try again",
  retrying = false,
  className,
}: ErrorCardProps) {
  const [showDetails, setShowDetails] = useState(false);
  const category = categoryProp ?? categoriseError(error);
  const meta = CATEGORY_META[category];
  const title = titleProp ?? meta.title;
  const showRetry = meta.canRetry && onRetry;

  return (
    <div
      className={cn(
        "rounded-xl border-2 border-destructive bg-destructive/5 p-5",
        className,
      )}
      role="alert"
      aria-live="assertive"
    >
      {/* Header row */}
      <div className="flex items-start gap-4">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-destructive/15">
          <AlertTriangle className="h-6 w-6 text-destructive" />
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-base font-semibold text-destructive">{title}</h3>
            <span className="rounded-full bg-destructive/15 px-2 py-0.5 text-xs font-medium text-destructive">
              {meta.badge}
            </span>
          </div>
          <p className="mt-1 text-sm leading-relaxed text-foreground/80">
            {meta.explanation}
            {detail && <> {detail}</>}
          </p>
        </div>
      </div>

      {/* Technical details toggle */}
      {error && (
        <div className="mt-3">
          <button
            type="button"
            onClick={() => setShowDetails((v) => !v)}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            {showDetails ? (
              <ChevronUp className="h-3.5 w-3.5" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5" />
            )}
            {showDetails ? "Hide" : "Show"} technical details
          </button>
          {showDetails && (
            <pre className="mt-2 max-h-40 overflow-auto rounded-md bg-black/10 p-3 text-[11px] leading-relaxed text-destructive/80 whitespace-pre-wrap break-words border border-destructive/20">
              {error}
            </pre>
          )}
        </div>
      )}

      {/* Actions */}
      {(showRetry || category === "credits") && (
        <div className="mt-4 flex flex-wrap gap-2">
          {showRetry && (
            <Button
              size="sm"
              variant="destructive"
              onClick={onRetry}
              disabled={retrying}
              className="gap-1.5"
            >
              {retrying ? (
                <>
                  <RefreshCcw className="h-3.5 w-3.5 animate-spin" />
                  Retrying…
                </>
              ) : (
                <>
                  <RefreshCcw className="h-3.5 w-3.5" />
                  {retryLabel}
                </>
              )}
            </Button>
          )}
          {(category === "credits" || category === "infra") && (
            <Button size="sm" variant="outline" className="gap-1.5" asChild>
              <a href="mailto:support@bluhands.app">
                <LifeBuoy className="h-3.5 w-3.5" />
                Contact support
              </a>
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
