// Authentication helpers for the internal UI.
//
// The access token is stored in an httpOnly cookie set by the API, so it is
// NOT readable from JavaScript. Auth state is therefore derived by calling
// `GET /api/auth/me` rather than inspecting a token in localStorage.

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { API_BASE_URL, authedFetch, UnauthorizedError } from "@/lib/api";

export interface CurrentUser {
  id: string;
  email: string;
}

export class LoginError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = "LoginError";
    this.status = status;
  }
}

export async function login(email: string, password: string): Promise<CurrentUser> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ email: email.trim(), password }),
    });
  } catch {
    throw new LoginError("Could not reach the server. Please try again.");
  }

  if (res.status === 401) {
    throw new LoginError("Invalid email or password.", 401);
  }
  if (!res.ok) {
    throw new LoginError(`Login failed (HTTP ${res.status}).`, res.status);
  }
  return (await res.json()) as CurrentUser;
}

export async function logout(): Promise<void> {
  try {
    await fetch(`${API_BASE_URL}/api/auth/logout`, {
      method: "POST",
      credentials: "include",
    });
  } catch {
    // best-effort; cookie also expires on its own
  }
}

/**
 * Returns the current user, or null if not authenticated.
 */
export async function getCurrentUser(): Promise<CurrentUser | null> {
  try {
    const res = await authedFetch("/api/auth/me");
    if (!res.ok) return null;
    return (await res.json()) as CurrentUser;
  } catch (err) {
    if (err instanceof UnauthorizedError) return null;
    throw err;
  }
}

type AuthState = "loading" | "authenticated" | "unauthenticated";

/**
 * Client-side route guard for internal pages. Redirects to /login when the
 * user is not authenticated. Returns the current user once authenticated.
 */
export function useRequireAuth(): { state: AuthState; user: CurrentUser | null } {
  const router = useRouter();
  const [state, setState] = useState<AuthState>("loading");
  const [user, setUser] = useState<CurrentUser | null>(null);

  useEffect(() => {
    let active = true;
    getCurrentUser()
      .then((u) => {
        if (!active) return;
        if (u) {
          setUser(u);
          setState("authenticated");
        } else {
          setState("unauthenticated");
          router.replace("/login");
        }
      })
      .catch(() => {
        if (!active) return;
        setState("unauthenticated");
        router.replace("/login");
      });
    return () => {
      active = false;
    };
  }, [router]);

  return { state, user };
}
