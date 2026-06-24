"use client";

import { Check } from "lucide-react";

import { cn } from "@/lib/utils";
import { STEPS } from "@/lib/state";

const LABELS: Record<(typeof STEPS)[number], string> = {
  account: "Account",
  business: "Business",
  brand: "Brand",
  catalog: "Catalog",
  domain: "Domain",
  review: "Review",
  build: "Build",
};

export function Stepper({ current }: { current: number }) {
  return (
    <ol
      className={cn(
        "flex flex-nowrap items-center gap-x-1 overflow-x-auto",
        "[-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden",
      )}
    >
      {STEPS.map((step, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <li key={step} className="flex flex-none items-center gap-1.5">
            <span
              className={cn(
                "flex h-7 w-7 flex-none items-center justify-center rounded-full text-xs font-semibold",
                done && "bg-success text-success-foreground",
                active && "bg-primary text-primary-foreground",
                !done && !active && "bg-muted text-muted-foreground",
              )}
            >
              {done ? <Check className="h-4 w-4" /> : i + 1}
            </span>
            <span
              className={cn(
                "whitespace-nowrap text-sm",
                active ? "font-medium text-foreground" : "text-muted-foreground",
              )}
            >
              {LABELS[step]}
            </span>
            {i < STEPS.length - 1 && <span className="mx-1 h-px w-4 flex-none bg-border" />}
          </li>
        );
      })}
    </ol>
  );
}
