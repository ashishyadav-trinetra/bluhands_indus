"use client";

// Wizard state: a reducer for navigation + a deep-merge update for the collected
// data. Kept pure (reducer is exported and unit-tested) and small.

import { createContext, useContext, useMemo, useReducer } from "react";

import type { ClarifyAnswer, ClarifyQuestion, Industry, OnboardingData } from "./types";

export const STEPS = [
  "account",
  "business",
  "brand",
  "catalog",
  "domain",
  "review",
  "build",
] as const;

export type StepId = (typeof STEPS)[number];

export interface WizardState {
  stepIndex: number;
  data: OnboardingData;
  buildId: string | null;
  // Auth state (set after Supabase login + /auth/me)
  accessToken: string | null;
  orgId: string | null;
  isAdmin: boolean;
  // Tenant (set after createTenant)
  tenantId: string | null;
  // Clarify/enhance (set during review step)
  clarifyQuestions: ClarifyQuestion[] | null;
  clarifyAnswers: ClarifyAnswer[];
  enhancedPrompt: string | null;
}

export type DeepPartial<T> = {
  [K in keyof T]?: T[K] extends ReadonlyArray<unknown>
    ? T[K]
    : T[K] extends object
      ? DeepPartial<T[K]>
      : T[K];
};

export type Action =
  | { type: "next" }
  | { type: "back" }
  | { type: "goto"; index: number }
  | { type: "update"; patch: DeepPartial<OnboardingData> }
  | { type: "setBuild"; buildId: string }
  | { type: "setAuth"; accessToken: string; orgId: string; isAdmin: boolean }
  | { type: "setTenant"; tenantId: string }
  | { type: "setClarify"; questions: ClarifyQuestion[] }
  | { type: "setClarifyAnswers"; answers: ClarifyAnswer[] }
  | { type: "setEnhanced"; enhancedPrompt: string };

/** Fallback used when no industry is injected via OnboardingProvider. */
export const DEFAULT_INDUSTRY: Industry = "ecommerce";

export const initialData: OnboardingData = {
  industry: DEFAULT_INDUSTRY,
  account: { fullName: "", email: "", organizationName: "" },
  business: { storeName: "", category: "Apparel", country: "IN", currency: "INR", supportEmail: "" },
  brand: { tagline: "", primaryColor: "#2d3e63", accentColor: "#e2725b", vibe: "minimal", logoName: null },
  catalog: {
    choice: "scratch",
    products: [{ id: "p_1", name: "", price: "", stock: "", images: [] }],
  },
  domain: { mode: "subdomain", domain: "", dnsRecords: [], purchased: false },
};

export const initialState: WizardState = {
  stepIndex: 0,
  data: initialData,
  buildId: null,
  accessToken: null,
  orgId: null,
  isAdmin: false,
  tenantId: null,
  clarifyQuestions: null,
  clarifyAnswers: [],
  enhancedPrompt: null,
};

function mergeData(base: OnboardingData, patch: DeepPartial<OnboardingData>): OnboardingData {
  const out: OnboardingData = { ...base };
  for (const key of Object.keys(patch) as (keyof OnboardingData)[]) {
    const value = patch[key];
    if (value && typeof value === "object" && !Array.isArray(value)) {
      out[key] = { ...(base[key] as object), ...(value as object) } as never;
    } else if (value !== undefined) {
      out[key] = value as never;
    }
  }
  return out;
}

export function reducer(state: WizardState, action: Action): WizardState {
  switch (action.type) {
    case "next":
      return { ...state, stepIndex: Math.min(state.stepIndex + 1, STEPS.length - 1) };
    case "back":
      return { ...state, stepIndex: Math.max(state.stepIndex - 1, 0) };
    case "goto":
      return { ...state, stepIndex: Math.max(0, Math.min(action.index, STEPS.length - 1)) };
    case "update":
      return { ...state, data: mergeData(state.data, action.patch) };
    case "setBuild":
      return { ...state, buildId: action.buildId };
    case "setAuth":
      return { ...state, accessToken: action.accessToken, orgId: action.orgId, isAdmin: action.isAdmin };
    case "setTenant":
      return { ...state, tenantId: action.tenantId };
    case "setClarify":
      return { ...state, clarifyQuestions: action.questions };
    case "setClarifyAnswers":
      return { ...state, clarifyAnswers: action.answers };
    case "setEnhanced":
      return { ...state, enhancedPrompt: action.enhancedPrompt };
    default:
      return state;
  }
}

interface Ctx {
  state: WizardState;
  dispatch: React.Dispatch<Action>;
}

const OnboardingContext = createContext<Ctx | null>(null);

interface OnboardingProviderProps {
  children: React.ReactNode;
  /** Industry locked for this deployment. Defaults to "ecommerce".
   *  Set via NEXT_PUBLIC_INDUSTRY at build time for each branded product. */
  industry?: Industry;
}

export function OnboardingProvider({ children, industry }: OnboardingProviderProps) {
  const seed = industry && industry !== DEFAULT_INDUSTRY
    ? { ...initialState, data: { ...initialData, industry } }
    : initialState;
  const [state, dispatch] = useReducer(reducer, seed);
  const value = useMemo(() => ({ state, dispatch }), [state]);
  return <OnboardingContext.Provider value={value}>{children}</OnboardingContext.Provider>;
}

export function useOnboarding(): Ctx {
  const ctx = useContext(OnboardingContext);
  if (!ctx) throw new Error("useOnboarding must be used within OnboardingProvider");
  return ctx;
}
