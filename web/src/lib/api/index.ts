import type { ApiClient } from "./client";
import { HttpApiClient } from "./http";
import { MockApiClient } from "./mock/client";

/**
 * Picks the implementation once, from build-time env (NEXT_PUBLIC_* values are
 * inlined by Next). This is the only file that knows two clients exist.
 */
function createApi(): ApiClient {
  if (process.env.NEXT_PUBLIC_API_MODE === "live") {
    const base = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (!base) throw new Error("NEXT_PUBLIC_API_BASE_URL is required when NEXT_PUBLIC_API_MODE=live");
    return new HttpApiClient(base);
  }
  return new MockApiClient();
}

export const api: ApiClient = createApi();
export const isMockMode = process.env.NEXT_PUBLIC_API_MODE !== "live";
export type { ApiClient } from "./client";
