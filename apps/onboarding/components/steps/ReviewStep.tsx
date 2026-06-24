"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Loader2 } from "lucide-react";

import { getApi } from "@/lib/api";
import { useOnboarding } from "@/lib/state";
import type { ClarifyAnswer, ClarifyQuestion } from "@/lib/types";
import { StepShell } from "./StepShell";

// ---- Summary row ----

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4 border-t border-border py-2 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right font-medium">{value}</span>
    </div>
  );
}

// ---- Clarify question card ----

function QuestionCard({
  question,
  answer,
  onChange,
}: {
  question: ClarifyQuestion;
  answer: ClarifyAnswer;
  onChange: (a: ClarifyAnswer) => void;
}) {
  const toggle = (opt: string) => {
    if (question.kind === "single") {
      onChange({ ...answer, selected: [opt] });
    } else {
      const already = answer.selected.includes(opt);
      onChange({
        ...answer,
        selected: already ? answer.selected.filter((s) => s !== opt) : [...answer.selected, opt],
      });
    }
  };

  return (
    <div className="rounded-md border border-border p-4">
      <p className="mb-3 text-sm font-medium">{question.text}</p>
      <div className="space-y-2">
        {question.options.map((opt) => {
          const selected = answer.selected.includes(opt);
          return (
            <button
              key={opt}
              type="button"
              onClick={() => toggle(opt)}
              className={`w-full rounded-md border px-3 py-2 text-left text-sm transition-colors ${
                selected
                  ? "border-primary bg-primary/10 font-medium text-primary"
                  : "border-border hover:border-primary/50"
              }`}
            >
              {opt}
            </button>
          );
        })}
        {question.allow_other && (
          <input
            type="text"
            placeholder="Something else…"
            value={answer.other ?? ""}
            onChange={(e) => onChange({ ...answer, other: e.target.value })}
            className="w-full rounded-md border border-border bg-card px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          />
        )}
      </div>
    </div>
  );
}

// ---- Main component ----

type Phase = "summary" | "clarifying" | "clarify-answers" | "enhancing" | "plan" | "building";

function buildPrompt(data: ReturnType<typeof useOnboarding>["state"]["data"]): string {
  const { business, brand, catalog } = data;
  const productCount = catalog.products.filter((p) => p.name.trim()).length;
  return [
    `Build a ${brand.vibe} ecommerce storefront for ${business.storeName}`,
    business.category !== "Apparel" ? `selling ${business.category}` : "",
    productCount > 0 ? `with ${productCount} product${productCount === 1 ? "" : "s"}` : "",
    business.currency !== "INR" ? `in ${business.currency}` : "",
  ]
    .filter(Boolean)
    .join(", ")
    .replace(/,\s*$/, ".")
    .replace(/([^.])$/, "$1.");
}

export function ReviewStep() {
  const { state, dispatch } = useOnboarding();
  const { account, business, brand, catalog, domain } = state.data;
  const [phase, setPhase] = useState<Phase>("summary");
  const [answers, setAnswers] = useState<ClarifyAnswer[]>([]);
  const [planSummary, setPlanSummary] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const namedProducts = catalog.products.filter((p) => p.name.trim() !== "");

  // Auto-load clarify questions when we reach this step.
  useEffect(() => {
    if (state.clarifyQuestions) {
      const initial = state.clarifyQuestions.map((q) => ({
        question_id: q.id,
        selected: [] as string[],
      }));
      setAnswers(initial);
      setPhase("clarify-answers");
      return;
    }
    setPhase("clarifying");
    const prompt = buildPrompt(state.data);
    getApi()
      .clarify({
        prompt,
        industry: state.data.industry,
        brand: state.data.brand,
        business: state.data.business,
        products: namedProducts,
      })
      .then((result) => {
        dispatch({ type: "setClarify", questions: result.questions });
        const initial = result.questions.map((q) => ({
          question_id: q.id,
          selected: [] as string[],
        }));
        setAnswers(initial);
        setPhase("clarify-answers");
      })
      .catch(() => {
        // If clarify fails, skip straight to plain review.
        setPhase("summary");
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const questions = state.clarifyQuestions ?? [];

  const onEnhance = async () => {
    setPhase("enhancing");
    setError(null);
    dispatch({ type: "setClarifyAnswers", answers });
    try {
      const prompt = buildPrompt(state.data);
      const result = await getApi().enhance({
        prompt,
        industry: state.data.industry,
        clarifications: answers,
      });
      dispatch({ type: "setEnhanced", enhancedPrompt: result.enhanced_prompt });
      setPlanSummary(result.summary);
      setPhase("plan");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Enhancement failed.");
      setPhase("clarify-answers");
    }
  };

  const onBuild = async () => {
    setPhase("building");
    setError(null);
    try {
      const orgId = state.orgId ?? "current";
      const tenantId = state.tenantId ?? "current";
      const { buildId } = await getApi().startBuild({
        tenantId,
        orgId,
        brand,
        catalog,
        domain,
        clarifications: state.clarifyAnswers,
        enhancedPrompt: state.enhancedPrompt ?? undefined,
      });
      dispatch({ type: "setBuild", buildId });
      dispatch({ type: "next" });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start build.");
      setPhase("plan");
    }
  };

  // --- Summary phase (shown while clarify loads) ---
  if (phase === "summary" || phase === "clarifying") {
    return (
      <StepShell
        title="Review & build"
        description="Confirm the details. Then we'll build and deploy your store."
        onNext={() => {}} // disabled while loading
        nextLabel={phase === "clarifying" ? "Loading questions…" : "Continue"}
        nextDisabled
      >
        <div>
          <Row label="Account" value={`${account.fullName} · ${account.email}`} />
          <Row label="Store" value={`${business.storeName} (${business.category})`} />
          <Row label="Currency" value={`${business.currency} · ${business.country}`} />
          <Row label="Brand" value={`${brand.vibe}${brand.tagline ? ` · "${brand.tagline}"` : ""}`} />
          <Row label="Catalog" value={namedProducts.length === 0 ? "No products yet" : `${namedProducts.length} product${namedProducts.length === 1 ? "" : "s"}`} />
          <Row label="Web address" value={domain.domain || "—"} />
        </div>
        {phase === "clarifying" && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>Loading a few questions to personalise your build…</span>
          </div>
        )}
      </StepShell>
    );
  }

  // --- Clarify answers phase ---
  if (phase === "clarify-answers") {
    const answered = answers.every(
      (a) => a.selected.length > 0 || (a.other && a.other.trim() !== ""),
    );
    return (
      <StepShell
        title="A few quick questions"
        description="Your answers help us build exactly what you need."
        onNext={onEnhance}
        nextLabel="Review plan"
        nextDisabled={!answered}
      >
        <div className="space-y-4">
          {questions.map((q, i) => (
            <QuestionCard
              key={q.id}
              question={q}
              answer={answers[i] ?? { question_id: q.id, selected: [] }}
              onChange={(a) => {
                const next = [...answers];
                next[i] = a;
                setAnswers(next);
              }}
            />
          ))}
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
      </StepShell>
    );
  }

  // --- Enhancing spinner ---
  if (phase === "enhancing") {
    return (
      <StepShell title="Planning your build" description="" onNext={() => {}} nextLabel="Please wait…" nextDisabled>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span>Generating a build plan from your answers…</span>
        </div>
      </StepShell>
    );
  }

  // --- Plan review phase ---
  if (phase === "plan") {
    return (
      <StepShell
        title="Your build plan"
        description="Here's what we're going to build. Hit 'Build my store' when you're ready."
        onNext={onBuild}
        nextLabel="Build my store"
        nextDisabled={false}
      >
        {planSummary && (
          <div className="rounded-md border border-border bg-card p-4 text-sm">
            <p className="font-medium text-foreground">{planSummary}</p>
          </div>
        )}
        <div>
          <Row label="Account" value={`${account.fullName} · ${account.email}`} />
          <Row label="Store" value={`${business.storeName} (${business.category})`} />
          <Row label="Domain" value={domain.domain || "Auto-assigned"} />
        </div>
        <p className="text-xs text-muted-foreground">
          Building usually takes a couple of minutes. You can watch the progress on the next screen.
        </p>
        {error && <p className="text-sm text-destructive">{error}</p>}
      </StepShell>
    );
  }

  // --- Building spinner (brief, before transition to BuildStep) ---
  return (
    <StepShell title="Starting build…" description="" onNext={() => {}} nextLabel="Please wait…" nextDisabled>
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span>Submitting your build request…</span>
      </div>
    </StepShell>
  );
}
