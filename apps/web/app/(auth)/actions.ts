"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ACCESS_COOKIE, API_BASE, ApiRequestError, REFRESH_COOKIE, WORKSPACE_COOKIE, apiFetch } from "@/lib/api";
import type { Workspace } from "@/lib/types";

export type FormState = { error: string | null };

type TokenResponse = {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  user_id: string;
  organization_id: string | null;
};

/**
 * Tokens are stored httpOnly so no script in the page can read them, and a leaked XSS
 * payload cannot exfiltrate a session.
 */
async function storeSession(tokens: TokenResponse): Promise<void> {
  const jar = await cookies();
  const secure = process.env.NODE_ENV === "production";
  jar.set(ACCESS_COOKIE, tokens.access_token, {
    httpOnly: true,
    sameSite: "lax",
    secure,
    path: "/",
    maxAge: tokens.expires_in,
  });
  jar.set(REFRESH_COOKIE, tokens.refresh_token, {
    httpOnly: true,
    sameSite: "lax",
    secure,
    path: "/",
    maxAge: 60 * 60 * 24 * 30,
  });
}

export async function login(_state: FormState, formData: FormData): Promise<FormState> {
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");
  const mfaCode = String(formData.get("mfa_code") ?? "").trim();

  if (!email || !password) return { error: "Enter your email address and password." };

  let tokens: TokenResponse;
  try {
    tokens = await apiFetch<TokenResponse>("/auth/login", {
      method: "POST",
      anonymous: true,
      body: { email, password, mfa_code: mfaCode || null },
    });
  } catch (error) {
    if (error instanceof ApiRequestError) return { error: error.error.message };
    return { error: "Sign-in is unavailable. Please try again." };
  }

  await storeSession(tokens);
  await selectWorkspaceAfterAuth(tokens.access_token);
  redirect("/dashboard");
}

export async function register(_state: FormState, formData: FormData): Promise<FormState> {
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");
  const fullName = String(formData.get("full_name") ?? "").trim();
  const organizationName = String(formData.get("organization_name") ?? "").trim();
  const seedDemo = formData.get("seed_demo") !== null;

  if (!email || !password) return { error: "Enter your email address and a password." };

  let tokens: TokenResponse;
  try {
    tokens = await apiFetch<TokenResponse>("/auth/register", {
      method: "POST",
      anonymous: true,
      body: {
        email,
        password,
        full_name: fullName || null,
        organization_name: organizationName || null,
        seed_demo_workspace: seedDemo,
      },
    });
  } catch (error) {
    if (error instanceof ApiRequestError) {
      const fields = error.error.details?.fields as Array<{ message: string }> | undefined;
      const requirements = error.error.details?.requirements as string[] | undefined;
      if (requirements?.length) return { error: `Password ${requirements.join(", ")}.` };
      if (fields?.length) return { error: fields.map((field) => field.message).join(" ") };
      return { error: error.error.message };
    }
    return { error: "Registration is unavailable. Please try again." };
  }

  await storeSession(tokens);
  await selectWorkspaceAfterAuth(tokens.access_token);
  redirect("/dashboard");
}

/** Resolve and remember the workspace the user lands in. */
async function selectWorkspaceAfterAuth(accessToken: string): Promise<void> {
  try {
    const response = await fetch(
      `${API_BASE}/api/v1/workspaces`,
      { headers: { Authorization: `Bearer ${accessToken}` }, cache: "no-store" },
    );
    if (!response.ok) return;
    const workspaces = (await response.json()) as Workspace[];
    const preferred = workspaces.find((workspace) => workspace.is_demo) ?? workspaces[0];
    if (!preferred) return;
    const jar = await cookies();
    jar.set(WORKSPACE_COOKIE, preferred.id, {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: 60 * 60 * 24 * 30,
    });
  } catch {
    /* The workspace switcher lets the user pick one if this fails. */
  }
}

export async function logout(): Promise<void> {
  const jar = await cookies();
  const refreshToken = jar.get(REFRESH_COOKIE)?.value;
  if (refreshToken) {
    await apiFetch("/auth/logout", {
      method: "POST",
      anonymous: true,
      body: { refresh_token: refreshToken },
    }).catch(() => undefined);
  }
  jar.delete(ACCESS_COOKIE);
  jar.delete(REFRESH_COOKIE);
  jar.delete(WORKSPACE_COOKIE);
  redirect("/login");
}

export async function switchWorkspace(formData: FormData): Promise<void> {
  const workspaceId = String(formData.get("workspace_id") ?? "");
  if (workspaceId) {
    const jar = await cookies();
    jar.set(WORKSPACE_COOKIE, workspaceId, {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: 60 * 60 * 24 * 30,
    });
  }
  redirect("/dashboard");
}
