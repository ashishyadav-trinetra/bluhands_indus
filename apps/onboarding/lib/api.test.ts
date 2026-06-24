import { describe, expect, it } from "vitest";

import { BUILD_SEQUENCE, buildStateAt, MockApi } from "./api";

describe("buildStateAt", () => {
  it("walks the sequence and clamps at live", () => {
    expect(buildStateAt("b", 0).status).toBe("queued");
    expect(buildStateAt("b", BUILD_SEQUENCE.length - 1).status).toBe("live");
    expect(buildStateAt("b", 99).status).toBe("live"); // clamped
  });

  it("only exposes a preview url once live", () => {
    expect(buildStateAt("b", 0).previewUrl).toBeNull();
    const live = buildStateAt("b", BUILD_SEQUENCE.length - 1);
    expect(live.previewUrl).toContain("/b");
  });
});

describe("MockApi", () => {
  it("advances build status on each poll until live", async () => {
    const api = new MockApi();
    const { buildId } = await api.startBuild();
    const first = await api.getBuild(buildId);
    expect(first.status).toBe("queued");

    let last = first;
    for (let i = 0; i < BUILD_SEQUENCE.length; i++) last = await api.getBuild(buildId);
    expect(last.status).toBe("live");
    expect(last.previewUrl).not.toBeNull();
  });

  it("flags taken domains as unavailable", async () => {
    const api = new MockApi();
    expect((await api.checkDomain("freestore.com")).available).toBe(true);
    expect((await api.checkDomain("taken-store.com")).available).toBe(false);
  });

  it("returns an orgId from getMe", async () => {
    const api = new MockApi();
    const result = await api.getMe();
    expect(result.orgId).toBeTruthy();
    expect(typeof result.isAdmin).toBe("boolean");
  });
});
