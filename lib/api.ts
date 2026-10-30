// Client for the FinSight Python API (served under /api/py).
import { mutate } from "swr";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function handle<T>(response: Response): Promise<T> {
  if (response.status === 401 && typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
    window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
  }
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail)) message = "Please check the values you entered.";
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(message, response.status);
  }
  return response.json() as Promise<T>;
}

export const fetcher = <T,>(path: string): Promise<T> =>
  fetch(`/api/py${path}`, { credentials: "same-origin" }).then((r) => handle<T>(r));

async function send<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/py${path}`, {
    method,
    credentials: "same-origin",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return handle<T>(response);
}

export const api = {
  post: <T = unknown,>(path: string, body?: unknown) => send<T>("POST", path, body ?? {}),
  put: <T = unknown,>(path: string, body: unknown) => send<T>("PUT", path, body),
  del: <T = unknown,>(path: string) => send<T>("DELETE", path),
};

/** Re-fetch every cached query so all pages reflect a change. */
export function refreshAll() {
  return mutate(() => true);
}

export function queryString(params: Record<string, string | number | string[] | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === "") continue;
    if (Array.isArray(value)) {
      if (value.length) search.set(key, value.join(","));
    } else {
      search.set(key, String(value));
    }
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}
