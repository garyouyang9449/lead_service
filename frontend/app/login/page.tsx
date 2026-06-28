"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { login, LoginError } from "@/lib/auth";

type Status = "idle" | "submitting" | "error";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!email.trim() || !password) {
      setError("Email and password are required.");
      setStatus("error");
      return;
    }

    setStatus("submitting");
    try {
      await login(email, password);
      router.replace("/leads");
    } catch (err) {
      const message =
        err instanceof LoginError
          ? err.message
          : "Something went wrong. Please try again.";
      setError(message);
      setStatus("error");
    }
  }

  const submitting = status === "submitting";

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4 py-12">
      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm sm:p-8">
        <header className="mb-6">
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">
            Attorney sign in
          </h1>
          <p className="mt-1.5 text-sm text-gray-600">
            Sign in to review and manage submitted leads.
          </p>
        </header>

        <form onSubmit={handleSubmit} noValidate className="space-y-5">
          <div>
            <label
              htmlFor="email"
              className="mb-1.5 block text-sm font-medium text-gray-800"
            >
              Email
            </label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              value={email}
              disabled={submitting}
              onChange={(e) => setEmail(e.target.value)}
              className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 shadow-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:ring-offset-1 disabled:opacity-60"
            />
          </div>

          <div>
            <label
              htmlFor="password"
              className="mb-1.5 block text-sm font-medium text-gray-800"
            >
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              value={password}
              disabled={submitting}
              onChange={(e) => setPassword(e.target.value)}
              className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 shadow-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:ring-offset-1 disabled:opacity-60"
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg bg-gray-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-900 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? "Signing in…" : "Sign in"}
          </button>

          {error && (
            <div
              role="alert"
              className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-800"
            >
              {error}
            </div>
          )}
        </form>
      </div>
    </main>
  );
}
