"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useRequireAuth } from "@/lib/auth";
import {
  getLead,
  updateLeadState,
  UnauthorizedError,
  type LeadDetailResponse,
} from "@/lib/api";
import StateBadge from "@/components/StateBadge";

type LoadState = "loading" | "loaded" | "not_found" | "error";

export default function LeadDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { state: authState } = useRequireAuth();
  const router = useRouter();

  const [lead, setLead] = useState<LeadDetailResponse | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);

  const [updating, setUpdating] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    if (authState !== "authenticated") return;
    let active = true;

    setLoadState("loading");
    getLead(id)
      .then((data) => {
        if (!active) return;
        setLead(data);
        setLoadState("loaded");
      })
      .catch((err) => {
        if (!active) return;
        if (err instanceof UnauthorizedError) {
          router.replace("/login");
          return;
        }
        if (
          err &&
          typeof err === "object" &&
          "status" in err &&
          (err as { status?: number }).status === 404
        ) {
          setLoadState("not_found");
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load lead.");
        setLoadState("error");
      });

    return () => {
      active = false;
    };
  }, [authState, id, router]);

  async function handleMarkReachedOut() {
    setActionError(null);
    setUpdating(true);
    try {
      const updated = await updateLeadState(id, "REACHED_OUT");
      setLead((prev) => (prev ? { ...prev, ...updated } : prev));
    } catch (err) {
      if (err instanceof UnauthorizedError) {
        router.replace("/login");
        return;
      }
      setActionError(
        err instanceof Error ? err.message : "Could not update the lead.",
      );
    } finally {
      setUpdating(false);
    }
  }

  if (authState === "loading") {
    return <CenteredMessage>Loading…</CenteredMessage>;
  }
  if (authState === "unauthenticated") {
    return null;
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-10">
      <Link
        href="/leads"
        className="text-sm font-medium text-gray-500 underline hover:text-gray-800"
      >
        ← Back to leads
      </Link>

      {loadState === "loading" && (
        <p className="mt-6 text-sm text-gray-500">Loading lead…</p>
      )}

      {loadState === "not_found" && (
        <div className="mt-6 rounded-2xl border border-dashed border-gray-300 bg-white p-10 text-center text-sm text-gray-500">
          This lead could not be found.
        </div>
      )}

      {loadState === "error" && (
        <div
          role="alert"
          className="mt-6 rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-800"
        >
          {error}
        </div>
      )}

      {loadState === "loaded" && lead && (
        <div className="mt-6 rounded-2xl border border-gray-200 bg-white p-6 shadow-sm sm:p-8">
          <div className="mb-6 flex items-start justify-between gap-4">
            <h1 className="text-2xl font-bold tracking-tight text-gray-900">
              {lead.first_name} {lead.last_name}
            </h1>
            <StateBadge state={lead.state} />
          </div>

          <dl className="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-[8rem_1fr]">
            <Detail label="First name" value={lead.first_name} />
            <Detail label="Last name" value={lead.last_name} />
            <Detail label="Email">
              <a
                href={`mailto:${lead.email}`}
                className="text-gray-900 underline hover:text-gray-600"
              >
                {lead.email}
              </a>
            </Detail>
            <Detail label="Resume">
              <a
                href={lead.resume_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-gray-900 underline hover:text-gray-600"
              >
                {lead.resume_filename}
              </a>
            </Detail>
            <Detail label="Submitted" value={formatDate(lead.created_at)} />
            <Detail label="Updated" value={formatDate(lead.updated_at)} />
          </dl>

          <div className="mt-8 border-t border-gray-100 pt-6">
            {lead.state === "PENDING" ? (
              <>
                <button
                  type="button"
                  onClick={handleMarkReachedOut}
                  disabled={updating}
                  className="rounded-lg bg-gray-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-900 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {updating ? "Updating…" : "Mark as Reached Out"}
                </button>
                {actionError && (
                  <p role="alert" className="mt-3 text-sm text-red-600">
                    {actionError}
                  </p>
                )}
              </>
            ) : (
              <p className="text-sm text-gray-500">
                This lead has already been marked as reached out.
              </p>
            )}
          </div>
        </div>
      )}
    </main>
  );
}

function Detail({
  label,
  value,
  children,
}: {
  label: string;
  value?: string;
  children?: React.ReactNode;
}) {
  return (
    <>
      <dt className="text-sm font-medium text-gray-500">{label}</dt>
      <dd className="text-sm text-gray-900">{children ?? value}</dd>
    </>
  );
}

function CenteredMessage({ children }: { children: React.ReactNode }) {
  return (
    <main className="flex min-h-screen items-center justify-center text-sm text-gray-500">
      {children}
    </main>
  );
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}
