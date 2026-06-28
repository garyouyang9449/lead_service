"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useRequireAuth, logout } from "@/lib/auth";
import {
  listLeads,
  UnauthorizedError,
  type LeadResponse,
} from "@/lib/api";
import StateBadge from "@/components/StateBadge";

type LoadState = "loading" | "loaded" | "error";

export default function LeadsPage() {
  const { state: authState, user } = useRequireAuth();
  const router = useRouter();
  const [leads, setLeads] = useState<LeadResponse[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authState !== "authenticated") return;
    let active = true;

    setLoadState("loading");
    listLeads()
      .then((data) => {
        if (!active) return;
        setLeads(data);
        setLoadState("loaded");
      })
      .catch((err) => {
        if (!active) return;
        if (err instanceof UnauthorizedError) {
          router.replace("/login");
          return;
        }
        setError(
          err instanceof Error ? err.message : "Failed to load leads.",
        );
        setLoadState("error");
      });

    return () => {
      active = false;
    };
  }, [authState, router]);

  async function handleLogout() {
    await logout();
    router.replace("/login");
  }

  if (authState === "loading") {
    return <CenteredMessage>Loading…</CenteredMessage>;
  }
  if (authState === "unauthenticated") {
    return null; // redirect in progress
  }

  return (
    <main className="mx-auto max-w-5xl px-4 py-10">
      <header className="mb-8 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">
            Leads
          </h1>
          <p className="mt-1 text-sm text-gray-600">
            Signed in as {user?.email}
          </p>
        </div>
        <button
          type="button"
          onClick={handleLogout}
          className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Sign out
        </button>
      </header>

      {loadState === "loading" && (
        <p className="text-sm text-gray-500">Loading leads…</p>
      )}

      {loadState === "error" && (
        <div
          role="alert"
          className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-800"
        >
          {error}
        </div>
      )}

      {loadState === "loaded" && leads.length === 0 && (
        <div className="rounded-2xl border border-dashed border-gray-300 bg-white p-10 text-center text-sm text-gray-500">
          No leads have been submitted yet.
        </div>
      )}

      {loadState === "loaded" && leads.length > 0 && (
        <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-gray-200 bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Email</th>
                <th className="px-4 py-3 font-medium">State</th>
                <th className="px-4 py-3 font-medium">Submitted</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {leads.map((lead) => (
                <tr key={lead.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900">
                    {lead.first_name} {lead.last_name}
                  </td>
                  <td className="px-4 py-3 text-gray-700">{lead.email}</td>
                  <td className="px-4 py-3">
                    <StateBadge state={lead.state} />
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {formatDate(lead.created_at)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      href={`/leads/${lead.id}`}
                      className="font-medium text-gray-900 underline hover:text-gray-600"
                    >
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
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
