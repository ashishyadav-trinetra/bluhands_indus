"use client";

import { Store } from "lucide-react";

import { STEPS, useOnboarding } from "@/lib/state";
import { Card } from "@/components/ui/card";
import { Stepper } from "@/components/Stepper";
import { AccountStep } from "@/components/steps/AccountStep";
import { BusinessStep } from "@/components/steps/BusinessStep";
import { BrandStep } from "@/components/steps/BrandStep";
import { CatalogStep } from "@/components/steps/CatalogStep";
import { DomainStep } from "@/components/steps/DomainStep";
import { ReviewStep } from "@/components/steps/ReviewStep";
import { BuildStep } from "@/components/steps/BuildStep";

export function Wizard() {
  const { state } = useOnboarding();
  const step = STEPS[state.stepIndex];

  return (
    <div className="min-h-screen">
      <div className="flex items-center justify-between border-b border-border px-4 py-3 sm:px-8">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <Store className="h-4 w-4" />
          </span>
          <span className="text-sm font-semibold">BluHands</span>
        </div>
        <span className="text-sm text-muted-foreground">
          Step {state.stepIndex + 1} of {STEPS.length}
        </span>
      </div>

      <div className="mx-auto max-w-4xl px-4 py-10 sm:px-8">
        <header className="mb-8">
          <p className="text-sm font-medium text-muted-foreground">BluHands</p>
          <h1 className="text-3xl font-bold tracking-tight">Create your store</h1>
        </header>

        {step !== "build" && (
          <div className="mb-8">
            <Stepper current={state.stepIndex} />
          </div>
        )}

        {step === "build" ? (
          <BuildStep />
        ) : (
          <Card className="p-6 sm:p-10">
            {step === "account" && <AccountStep />}
            {step === "business" && <BusinessStep />}
            {step === "brand" && <BrandStep />}
            {step === "catalog" && <CatalogStep />}
            {step === "domain" && <DomainStep />}
            {step === "review" && <ReviewStep />}
          </Card>
        )}
      </div>
    </div>
  );
}
