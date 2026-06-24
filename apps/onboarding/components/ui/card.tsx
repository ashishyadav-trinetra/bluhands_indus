import * as React from "react";

import { cn } from "@/lib/utils";

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("rounded-lg border border-border bg-card text-card-foreground shadow-sm", className)}
      {...props}
    />
  );
}

export function SelectableCard({
  selected,
  className,
  ...props
}: React.HTMLAttributes<HTMLButtonElement> & { selected?: boolean }) {
  return (
    <button
      type="button"
      className={cn(
        "rounded-lg border bg-card p-4 text-left transition-colors hover:bg-muted",
        selected ? "border-primary ring-2 ring-primary" : "border-border",
        className,
      )}
      {...props}
    />
  );
}
