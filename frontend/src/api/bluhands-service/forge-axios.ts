import axios from "axios";
import { getAccessToken } from "#/lib/supabase";

// Dedicated axios instance for the BluHands control-plane (Forge).
// Uses VITE_API_BASE_URL (nginx → control-plane on :8080).
// Injects the Supabase access token so the control-plane can JIT-provision
// the user and resolve their org membership.
export const forgeClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8080",
});

forgeClient.interceptors.request.use(async (config) => {
  try {
    const token = await getAccessToken();
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  } catch {
    // No Supabase session — request proceeds unauthenticated (will get 401).
  }
  return config;
});
