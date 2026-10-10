/**
 * Server-side API client.
 *
 * The browser never calls the API and never holds a token: the session lives in an
 * httpOnly cookie, read here on the server. That is also why no provider credential can
 * reach the client — nothing in this module runs in the browser.
 */

import "server-only";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

export const API_BASE =
  process.env.FINAGENT_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";
export const API_PREFIX = "/api/v1";

export const ACCESS_COOKIE = "finagent_access";
export const REFRESH_COOKIE = "finagent_refresh";
export const WORKSPACE_COOKIE = "finagent_workspace";

export type ApiError = {
  code: string;
  message: string;
  retryable: boolean;
  details: Record<string, unknown>;
  requestId: string | null;
};

export class ApiRequestError extends Error {
  readonly status: number;
  readonly error: ApiError;

  constructor(status: number, error: ApiError) {
    super(error.message);
    this.name = "ApiRequestError";
    this.status = status;
    this.error = error;
  }
}

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  workspaceId?: string | null;
  /** Skip the session cookie: used by sign-in and registration. */
  anonymous?: boolean;
  cache?: RequestCache;
  formData?: FormData;
};

const GENERIC_FAILURE: ApiError = {
  code: "INTERNAL_ERROR",
  message: "The service did not respond. Please try again.",
  retryable: true,
  details: {},
  requestId: null,
};

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, anonymous = false, workspaceId, cache = "no-store", formData } = options;

  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";

  if (!anonymous) {
    const jar = await cookies();
    const token = jar.get(ACCESS_COOKIE)?.value;
    if (!token) redirect("/login");
    headers.Authorization = `Bearer ${token}`;

    const workspace = workspaceId ?? jar.get(WORKSPACE_COOKIE)?.value;
    if (workspace) headers["X-Workspace-Id"] = workspace;
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${API_PREFIX}${path}`, {
      method,
      headers,
      body: formData ?? (body === undefined ? undefined : JSON.stringify(body)),
      cache,
    });
  } catch {
    throw new ApiRequestError(503, GENERIC_FAILURE);
  }

  if (response.status === 401 && !anonymous) redirect("/login");

  if (!response.ok) {
    let error = GENERIC_FAILURE;
    try {
      const payload = (await response.json()) as { error?: Partial<ApiError> };
      if (payload.error) {
        error = {
          code: payload.error.code ?? "INTERNAL_ERROR",
          message: payload.error.message ?? GENERIC_FAILURE.message,
          retryable: payload.error.retryable ?? false,
          details: (payload.error.details as Record<string, unknown>) ?? {},
          requestId: (payload.error as { request_id?: string }).request_id ?? null,
        };
      }
    } catch {
      /* The API always returns JSON; a non-JSON body means an infrastructure failure. */
    }
    throw new ApiRequestError(response.status, error);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** Fetch that renders an empty state instead of failing the page. */
export async function apiFetchOrNull<T>(path: string, options: RequestOptions = {}): Promise<T | null> {
  try {
    return await apiFetch<T>(path, options);
  } catch (error) {
    if (error instanceof ApiRequestError) return null;
    throw error;
  }
}

export async function currentWorkspaceId(): Promise<string | null> {
  const jar = await cookies();
  return jar.get(WORKSPACE_COOKIE)?.value ?? null;
}

export async function isSignedIn(): Promise<boolean> {
  const jar = await cookies();
  return Boolean(jar.get(ACCESS_COOKIE)?.value);
}
