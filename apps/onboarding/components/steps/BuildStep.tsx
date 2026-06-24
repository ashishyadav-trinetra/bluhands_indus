"use client";

import { useEffect, useRef, useState } from "react";
import { CheckCircle2, Globe, Loader2, Sparkles, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { getApi } from "@/lib/api";
import { useOnboarding } from "@/lib/state";
import type { BuildStatus, BuildState } from "@/lib/types";
import { cn } from "@/lib/utils";

const PHASES: { status: BuildStatus; label: string }[] = [
  { status: "queued", label: "Queued" },
  { status: "building", label: "Building your store" },
  { status: "self_testing", label: "Testing the storefront" },
  { status: "deploying", label: "Deploying" },
  { status: "live", label: "Live" },
];

const order = (s: BuildStatus) => PHASES.findIndex((p) => p.status === s);

export function BuildStep() {
  const { state } = useOnboarding();
  const { buildId } = state;
  const [build, setBuild] = useState<BuildState | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!buildId) return;
    let active = true;

    const poll = async () => {
      const orgId = state.orgId ?? "current";
      const tenantId = state.tenantId ?? "current";
      const next = await getApi().getBuild(buildId, tenantId, orgId);
      if (!active) return;
      setBuild(next);
      if (next.status !== "live" && next.status !== "failed") {
        timer.current = setTimeout(poll, 1000);
      }
    };
    poll();

    return () => {
      active = false;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [buildId]);

  const current = build?.status ?? "queued";
  const failed = current === "failed";
  const live = current === "live";
  const currentOrder = order(current);

  return (
    <Card className="p-6 sm:p-10">
      <div className="mx-auto max-w-md text-center">
        <span
          className={cn(
            "mx-auto flex h-16 w-16 items-center justify-center rounded-full",
            failed ? "bg-destructive/15 text-destructive" : "bg-primary text-primary-foreground",
          )}
        >
          {live ? (
            <Sparkles className="h-7 w-7" />
          ) : failed ? (
            <XCircle className="h-7 w-7" />
          ) : (
            <Loader2 className="h-7 w-7 animate-spin" />
          )}
        </span>

        <h2 className="mt-4 text-2xl font-bold tracking-tight">
          {live ? "Your store is live" : failed ? "Build failed" : "Building your store…"}
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">
          {live
            ? "We built your store with your products, brand, and domain. Share the link and start selling."
            : failed
              ? "Something went wrong. You can retry from your dashboard."
              : "Hang tight — this usually takes a couple of minutes."}
        </p>

        {!live && (
          <Card className="mt-6 p-5 text-left">
            <ol className="space-y-3">
              {PHASES.filter((p) => p.status !== "live").map((p) => {
                const idx = order(p.status);
                const done = currentOrder > idx;
                const isFailedHere = failed && currentOrder === idx;
                const inProgress = currentOrder === idx && !failed;
                return (
                  <li key={p.status} className="flex items-center gap-3 text-sm">
                    {isFailedHere ? (
                      <XCircle className="h-5 w-5 text-destructive" />
                    ) : done ? (
                      <CheckCircle2 className="h-5 w-5 text-success" />
                    ) : inProgress ? (
                      <Loader2 className="h-5 w-5 animate-spin text-primary" />
                    ) : (
                      <span className="h-5 w-5 rounded-full border border-border" />
                    )}
                    <span
                      className={cn(
                        isFailedHere
                          ? "text-destructive"
                          : done
                            ? "text-foreground"
                            : inProgress
                              ? "font-medium"
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

        {failed && (
          <div className="mt-6 flex items-center gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-4 text-left text-sm">
            <XCircle className="h-4 w-4 flex-none text-destructive" />
            <span>{build?.error ?? "Unknown error."}</span>
          </div>
        )}
      </div>
    </Card>
  );
}
