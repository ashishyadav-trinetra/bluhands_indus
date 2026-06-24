import { describe, expect, it } from "vitest";

import { initialState, reducer, STEPS } from "./state";

describe("wizard reducer", () => {
  it("advances and clamps at the last step", () => {
    let s = initialState;
    for (let i = 0; i < STEPS.length + 3; i++) s = reducer(s, { type: "next" });
    expect(s.stepIndex).toBe(STEPS.length - 1);
  });

  it("goes back and clamps at zero", () => {
    let s = { ...initialState, stepIndex: 1 };
    s = reducer(s, { type: "back" });
    s = reducer(s, { type: "back" });
    expect(s.stepIndex).toBe(0);
  });

  it("goto clamps into range", () => {
    expect(reducer(initialState, { type: "goto", index: 99 }).stepIndex).toBe(STEPS.length - 1);
    expect(reducer(initialState, { type: "goto", index: -5 }).stepIndex).toBe(0);
  });

  it("deep-merges nested data without dropping siblings", () => {
    const s = reducer(initialState, {
      type: "update",
      patch: { business: { storeName: "Acme" } },
    });
    expect(s.data.business.storeName).toBe("Acme");
    // currency (a sibling) must survive the partial update.
    expect(s.data.business.currency).toBe("INR");
  });

  it("replaces array fields wholesale", () => {
    const s = reducer(initialState, {
      type: "update",
      patch: { domain: { dnsRecords: [{ type: "A", name: "@", value: "1.2.3.4" }] } },
    });
    expect(s.data.domain.dnsRecords).toHaveLength(1);
  });

  it("stores the build id", () => {
    const s = reducer(initialState, { type: "setBuild", buildId: "bld_x" });
    expect(s.buildId).toBe("bld_x");
  });
});
