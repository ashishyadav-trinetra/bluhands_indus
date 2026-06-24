"use client";

import { useState } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getApi, setApiToken } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import { useOnboarding } from "@/lib/state";
import { StepShell } from "./StepShell";

export function AccountStep() {
  const { state, dispatch } = useOnboarding();
  const { account } = state.data;

  // Password is intentionally NOT in wizard state — it must never be persisted
  // beyond this component. It is consumed once by supabase.auth.signUp() and
  // then discarded automatically when the component unmounts.
  const [password, setPassword] = useState("");

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const set = (patch: Partial<typeof account>) =>
    dispatch({ type: "update", patch: { account: patch } });

  const valid =
    account.fullName.trim() !== "" &&
    /\S+@\S+\.\S+/.test(account.email) &&
    password.length >= 8 &&
    account.organizationName.trim() !== "";

  const onNext = async () => {
    setBusy(true);
    setError(null);
    try {
      // 1. Create Supabase user. Password never enters the wizard reducer.
      const { data: authData, error: signUpError } = await supabase.auth.signUp({
        email: account.email,
        password,
        options: { data: { full_name: account.fullName } },
      });
      if (signUpError) throw new Error(signUpError.message);

      const token = authData.session?.access_token;
      if (!token) {
        // Supabase requires email confirmation — advance without a token.
        dispatch({ type: "next" });
        return;
      }

      // 2. Inject token into the API client, then JIT-provision on the control plane.
      setApiToken(token);
      const { orgId, isAdmin } = await getApi().getMe();

      dispatch({ type: "setAuth", accessToken: token, orgId, isAdmin });
      dispatch({ type: "next" });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <StepShell
      title="Create your account"
      description="This is the login you'll use to manage your store."
      onNext={onNext}
      nextLabel={busy ? "Creating…" : "Continue"}
      nextDisabled={!valid || busy}
      showBack={false}
    >
      <div>
        <Label htmlFor="fullName">Your name</Label>
        <Input
          id="fullName"
          value={account.fullName}
          onChange={(e) => set({ fullName: e.target.value })}
          placeholder="Ashish Yadav"
        />
      </div>
      <div>
        <Label htmlFor="org">Business name</Label>
        <Input
          id="org"
          value={account.organizationName}
          onChange={(e) => set({ organizationName: e.target.value })}
          placeholder="Trinetra Labs"
        />
      </div>
      <div>
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          type="email"
          value={account.email}
          onChange={(e) => set({ email: e.target.value })}
          placeholder="you@example.com"
        />
      </div>
      <div>
        <Label htmlFor="password">Password</Label>
        <Input
          id="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="At least 8 characters"
        />
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
    </StepShell>
  );
}
