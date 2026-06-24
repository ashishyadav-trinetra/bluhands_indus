import { Wizard } from "@/components/Wizard";
import { OnboardingProvider } from "@/lib/state";
import type { Industry } from "@/lib/types";

// NEXT_PUBLIC_INDUSTRY is baked in at build time.
// Each branded product (ecommerce builder, CRM builder, …) sets this in its
// deploy environment — the wizard code is identical, only the industry differs.
const INDUSTRY = (process.env.NEXT_PUBLIC_INDUSTRY as Industry) || "ecommerce";

export default function Page() {
  return (
    <main className="min-h-screen">
      <OnboardingProvider industry={INDUSTRY}>
        <Wizard />
      </OnboardingProvider>
    </main>
  );
}
