import axios from "axios";
import { getAccessToken, refresh } from "#/lib/auth";

// Dedicated axios instance for the BluHands control-plane (Forge).
// Uses VITE_API_BASE_URL (nginx → control-plane on :8080).
// Injects the native access token; the HttpOnly refresh cookie rides along so
// an expired session can be renewed transparently.
export const forgeClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8080",
  withCredentials: true,
});

forgeClient.interceptors.request.use(async (config) => {
  const token = await getAccessToken();
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// One retry on 401: the access token may have expired mid-flight. Refresh once
// and replay. If the refresh also fails the user is genuinely signed out and
// the 401 propagates to the caller.
forgeClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (error.response?.status !== 401 || !original || original._retried) {
      return Promise.reject(error);
    }
    original._retried = true;

    const token = await refresh();
    if (!token) return Promise.reject(error);

    original.headers = { ...original.headers, Authorization: `Bearer ${token}` };
    return forgeClient(original);
  },
);
