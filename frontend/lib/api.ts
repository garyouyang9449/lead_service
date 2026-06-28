// Minimal fetch client for the public lead endpoint.
// Backend contract: POST /api/leads (multipart) -> 201 { ...lead } | { detail }.

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

export interface LeadSubmission {
  firstName: string;
  lastName: string;
  email: string;
  resume: File;
}

export interface LeadResponse {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  resume_filename: string;
  state: string;
  created_at: string;
  updated_at: string;
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
