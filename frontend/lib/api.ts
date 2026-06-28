// Minimal fetch client for the public lead endpoint.
// Backend contract: POST /api/leads (multipart) -> 201 { ...lead } | { detail }.

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

export { API_BASE_URL };

/**
 * Raised when an authenticated request is rejected (401). Callers should
 * redirect to /login.
 */
export class UnauthorizedError extends Error {
  constructor(message = "Your session has expired. Please log in again.") {
    super(message);
    this.name = "UnauthorizedError";
  }
}

/**
 * fetch wrapper for internal/authenticated endpoints. Sends the httpOnly auth
 * cookie via `credentials: "include"` and normalizes 401s to UnauthorizedError.
 */
export async function authedFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: "include",
  });
  if (res.status === 401) {
    throw new UnauthorizedError();
  }
  return res;
}

export interface LeadSubmission {
  firstName: string;
  lastName: string;
  email: string;
  resume: File;
}

export type LeadState = "PENDING" | "REACHED_OUT";

export interface LeadResponse {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  resume_filename: string;
  state: LeadState;
  created_at: string;
  updated_at: string;
}

export interface LeadDetailResponse extends LeadResponse {
  /** Presigned URL to download the resume file. */
  resume_url: string;
}

export class LeadSubmitError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = "LeadSubmitError";
    this.status = status;
  }
}

export async function submitLead(
  submission: LeadSubmission,
): Promise<LeadResponse> {
  const form = new FormData();
  form.append("first_name", submission.firstName.trim());
  form.append("last_name", submission.lastName.trim());
  form.append("email", submission.email.trim());
  form.append("resume", submission.resume, submission.resume.name);

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}/api/leads`, {
      method: "POST",
      body: form,
    });
  } catch {
    throw new LeadSubmitError(
      "Could not reach the server. Please try again.",
    );
  }

  if (!res.ok) {
    const detail = await extractDetail(res);
    throw new LeadSubmitError(detail, res.status);
  }

  return (await res.json()) as LeadResponse;
}

/**
 * Raised when an authenticated leads request fails for a non-401 reason.
 * 401s are surfaced as {@link UnauthorizedError} by `authedFetch`.
 */
export class LeadsRequestError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = "LeadsRequestError";
    this.status = status;
  }
}

/** Fetch all leads (internal, auth-guarded). */
export async function listLeads(): Promise<LeadResponse[]> {
  const res = await authedFetch("/api/leads");
  if (!res.ok) {
    throw new LeadsRequestError(await extractDetail(res), res.status);
  }
  return (await res.json()) as LeadResponse[];
}

/** Fetch a single lead with a presigned resume URL (internal, auth-guarded). */
export async function getLead(id: string): Promise<LeadDetailResponse> {
  const res = await authedFetch(`/api/leads/${id}`);
  if (!res.ok) {
    throw new LeadsRequestError(await extractDetail(res), res.status);
  }
  return (await res.json()) as LeadDetailResponse;
}

/** Transition a lead's state (e.g. PENDING -> REACHED_OUT). */
export async function updateLeadState(
  id: string,
  state: LeadState,
): Promise<LeadResponse> {
  const res = await authedFetch(`/api/leads/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ state }),
  });
  if (!res.ok) {
    throw new LeadsRequestError(await extractDetail(res), res.status);
  }
  return (await res.json()) as LeadResponse;
}

async function extractDetail(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail) && data.detail[0]?.msg) {
      return String(data.detail[0].msg);
    }
  } catch {
    // fall through to generic message
  }
  return `Submission failed (HTTP ${res.status}).`;
}
