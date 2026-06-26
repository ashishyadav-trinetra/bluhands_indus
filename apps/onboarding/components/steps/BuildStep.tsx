"use client";

import { useEffect, useRef, useState } from "react";
import { CheckCircle2, Globe, Loader2, Sparkles, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ErrorCard, categoriseError } from "@/components/ui/error-card";
import { getApi } from "@/lib/api";
import { useOnboarding } from "@/lib/state";
import type { BuildState, BuildStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const PHASES: { status: BuildStatus; label: string; description: string }[] = [
  { status: "queued",       label: "Queued",                description: "Waiting for a build slot" },
  { status: "building",     label: "Building your store",   description: "AI is writing your storefront" },
  { status: "self_testing", label: "Testing the storefront",description: "Running automated checks" },
  { status: "deploying",    label: "Deploying",             description: "Publishing to your domain" },
  { status: "live",         label: "Live",                  description: "Your store is online" },
];

const order = (s: BuildStatus) => PHASES.findIndex((p) => p.status === s);

// How many consecutive poll errors before we show the "can't reach server" banner.
const POLL_ERROR_THRESHOLD = 3;

export function BuildStep() {
  const { state } = useOnboarding();
  const { buildId } = state;

  const [build, setBuild] = useState<BuildState | null>(null);
  const [pollError, setPollError] = useState<string | null>(null);
  const [pollErrorCount, setPollErrorCount] = useState(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activeRef = useRef(true);

  useEffect(() => {
    if (!buildId) return;
    activeRef.current = true;

    const poll = async () => {
      try {
        const orgId = state.orgId ?? "current";
        const tenantId = state.tenantId ?? "current";
        const next = await getApi().getBuild(buildId, tenantId, orgId);
        if (!activeRef.current) return;
        setBuild(next);
        setPollError(null);
        setPollErrorCount(0);
        if (next.status !== "live" && next.status !== "failed") {
          timer.current = setTimeout(poll, 3000);
        }
      } catch (e) {
        if (!activeRef.current) return;
        const msg = e instanceof Error ? e.message : String(e);
        setPollErrorCount((n) => {
          const next = n + 1;
          if (next >= POLL_ERROR_THRESHOLD) setPollError(msg);
          return next;
        });
        // Keep polling — transient network blips shouldn't kill the progress view.
        timer.current = setTimeout(poll, 5000);
      }
    };

    poll();

    return () => {
      activeRef.current = false;
      if (timer.current) clearTimeout(timer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buildId]);

  const current = build?.status ?? "queued";
  const failed = current === "failed";
  const live = current === "live";
  const currentOrder = order(current);

  // ── Failed state ──────────────────────────────────────────────────────────
  if (failed) {
    const rawError = build?.error ?? null;
    const category = categoriseError(rawError);

    return (
      <Card className="p-6 sm:p-10">
        <div className="mx-auto max-w-lg">
          {/* Big failed header */}
          <div className="flex flex-col items-center text-center mb-6">
            <span className="flex h-16 w-16 items-center justify-center rounded-full bg-destructive/15">
              <XCircle className="h-9 w-9 text-destructive" />
            </span>
            <h2 className="mt-4 text-2xl font-bold tracking-tight text-destructive">
              Build failed
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Your store could not be built. See details below.
            </p>
          </div>

          {/* Categorised error card */}
          <ErrorCard
            error={rawError}
            category={category}
            onRetry={() => window.location.reload()}
            retryLabel="Retry build"
          />

          {/* Which phase it failed in */}
          <Card className="mt-4 p-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
              Progress at failure
            </p>
            <ol className="space-y-2">
              {PHASES.filter((p) => p.status !== "live").map((p) => {
                const idx = order(p.status);
                const done = currentOrder > idx;
                const failedHere = failed && currentOrder === idx;
                const pending = currentOrder < idx;
                return (
                  <li key={p.status} className="flex items-start gap-3 text-sm">
                    <span className="mt-0.5">
                      {failedHere ? (
                        <XCircle className="h-4.5 w-4.5 text-destructive" />
                      ) : done ? (
                        <CheckCircle2 className="h-4.5 w-4.5 text-green-500" />
                      ) : (
                        <span className="block h-4.5 w-4.5 rounded-full border border-border" />
                      )}
                    </span>
                    <div>
                      <span
                        className={cn(
                          "font-medium",
                          failedHere
                            ? "text-destructive"
                            : done
                              ? "text-foreground"
                              : "text-muted-foreground",
                        )}
                      >
                        {p.label}
                      </span>
                      {!pending && (
                        <span className="ml-2 text-xs text-muted-foreground">
                          {p.description}
                        </span>
                      )}
                    </div>
                  </li>
                );
              })}
            </ol>
          </Card>
        </div>
      </Card>
    );
  }

  // ── Normal / live state ───────────────────────────────────────────────────
  return (
    <Card className="p-6 sm:p-10">
      <div className="mx-auto max-w-md text-center">
        <span
          className={cn(
            "mx-auto flex h-16 w-16 items-center justify-center rounded-full",
            live ? "bg-primary" : "bg-primary/10",
          )}
        >
          {live ? (
            <Sparkles className="h-7 w-7 text-primary-foreground" />
          ) : (
            <Loader2 className="h-7 w-7 animate-spin text-primary" />
          )}
        </span>

        <h2 className="mt-4 text-2xl font-bold tracking-tight">
          {live ? "Your store is live 🎉" : "Building your store…"}
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">
          {live
            ? "We built your store with your products, brand, and domain. Share the link and start selling."
            : "Hang tight — this usually takes a couple of minutes."}
        </p>

        {/* Poll error banner (transient network issues) */}
        {pollError && !live && (
          <div className="mt-4">
            <ErrorCard
              error={pollError}
              category="network"
              title="Lost connection to server"
              detail="Still trying every 5 seconds — your build is likely still running."
            />
          </div>
        )}

        {/* Phase progress */}
        {!live && (
          <Card className="mt-6 p-5 text-left">
            <ol className="space-y-3">
              {PHASES.filter((p) => p.status !== "live").map((p) => {
                const idx = order(p.status);
                const done = currentOrder > idx;
                const inProgress = currentOrder === idx;
                return (
                  <li key={p.status} className="flex items-center gap-3 text-sm">
                    {done ? (
                      <CheckCircle2 className="h-5 w-5 shrink-0 text-green-500" />
                    ) : inProgress ? (
                      <Loader2 className="h-5 w-5 shrink-0 animate-spin text-primary" />
                    ) : (
                      <span className="h-5 w-5 shrink-0 rounded-full border border-border" />
                    )}
                    <span
                      className={cn(
                        done
                          ? "text-foreground"
                          : inProgress
                            ? "font-medium text-primary"
                            : "text-muted-foreground",
                      )}
                    >
                      {p.label}
                    </span>
                  </li>
                );
              })}
            </ol>
          </Card>
        )}

        {/* Live: link + actions */}
        {live && build?.previewUrl && (
          <div className="mt-6 space-y-4">
            <div className="inline-flex items-center gap-2 rounded-md border border-border px-4 py-2 text-sm">
              <Globe className="h-4 w-4 text-muted-foreground" />
              <span className="font-mono">{state.data.domain.domain || build.previewUrl}</span>
            </div>
            <div className="flex items-center justify-center gap-3">
              <a
                href={build.previewUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:opacity-90"
              >
                Visit storefront
              </a>
              <a
                href="/integrations"
                className="inline-flex h-10 items-center justify-center rounded-md border border-border px-4 text-sm font-medium text-muted-foreground transition-colors hover:border-primary/30 hover:text-foreground"
              >
                Connect apps
              </a>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
