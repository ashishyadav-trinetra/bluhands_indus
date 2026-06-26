"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useOnboarding } from "@/lib/state";

interface Props {
  title: string;
  description?: string;
  children: React.ReactNode;
  onNext?: () => void;
  nextLabel?: string;
  nextDisabled?: boolean;
  showBack?: boolean;
  hideNext?: boolean;
}

export function StepShell({
  title,
  description,
  children,
  onNext,
  nextLabel = "Continue",
  nextDisabled = false,
  showBack = true,
  hideNext = false,
}: Props) {
  const { state, dispatch } = useOnboarding();

  const handleNext = () => {
    if (onNext) onNext();
    else dispatch({ type: "next" });
  };

  return (
    <section>
      <h2 className="text-lg font-semibold">{title}</h2>
      {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      <div className="mt-6 space-y-5">{children}</div>
      <div className="mt-8 flex items-center justify-between border-t border-border pt-6">
        {showBack && state.stepIndex > 0 ? (
          <Button variant="ghost" onClick={() => dispatch({ type: "back" })}>
            <ChevronLeft className="h-4 w-4" />
            Back
          </Button>
        ) : (
          <span />
        )}
        {!hideNext && (
          <Button onClick={handleNext} disabled={nextDisabled}>
            {nextLabel}
            <ChevronRight className="h-4 w-4" />
          </Button>
        )}
      </div>
    </section>
  );
}
