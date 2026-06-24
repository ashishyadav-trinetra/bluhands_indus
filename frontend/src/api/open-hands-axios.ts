import axios, {
  AxiosError,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from "axios";
import { getAccessToken } from "#/lib/supabase";

export const openHands = axios.create({
  baseURL: `${window.location.protocol}//${import.meta.env.VITE_BACKEND_BASE_URL || window?.location.host}`,
});

// Inject Supabase access token into all API requests
openHands.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    try {
      const token = await getAccessToken();
      if (token && config.headers) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    } catch {
      // No Supabase session available — request proceeds unauthenticated.
      // The server will return 401 which is handled by the response interceptor.
    }
    return config;
  },
);

const EMAIL_NOT_VERIFIED = "EmailNotVerifiedError";

function checkForEmailVerificationError(data: unknown): boolean {
  if (typeof data === "string") {
    return data.includes(EMAIL_NOT_VERIFIED);
  }

  if (typeof data === "object" && data !== null) {
    const obj = data as Record<string, unknown>;

    if (typeof obj.message === "string") {
      return obj.message.includes(EMAIL_NOT_VERIFIED);
    }
    if (Array.isArray(obj.message)) {
      return obj.message.some(
        (msg) => typeof msg === "string" && msg.includes(EMAIL_NOT_VERIFIED),
      );
    }

    return Object.values(obj).some(
      (value) =>
        (typeof value === "string" && value.includes(EMAIL_NOT_VERIFIED)) ||
        (Array.isArray(value) &&
          value.some(
            (v) => typeof v === "string" && v.includes(EMAIL_NOT_VERIFIED),
          )),
    );
  }

  return false;
}

// Set up the global response interceptor
openHands.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: AxiosError) => {
    if (
      error.response?.status === 403 &&
      checkForEmailVerificationError(error.response?.data)
    ) {
      // Dispatch a DOM event instead of calling window.location.reload() directly.
      // This keeps the interceptor side-effect-free in test environments and lets
      // listeners (e.g. the root layout) decide how to respond.
      window.dispatchEvent(new CustomEvent("bluhands:email-unverified"));
    }

    return Promise.reject(error);
  },
);
