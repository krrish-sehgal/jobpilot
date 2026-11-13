import { describe, expect, it } from "vitest";
import { isSafeExternalUrl } from "./url";

describe("isSafeExternalUrl", () => {
  it("accepts only absolute http(s) URLs", () => {
    expect(isSafeExternalUrl("https://example.com/apply?x=1")).toBe(true);
    expect(isSafeExternalUrl("http://example.com")).toBe(true);
    expect(isSafeExternalUrl("javascript:alert(1)")).toBe(false);
    expect(isSafeExternalUrl("data:text/html,x")).toBe(false);
    expect(isSafeExternalUrl("/relative")).toBe(false);
    expect(isSafeExternalUrl("")).toBe(false);
  });
});
