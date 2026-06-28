"use client";

import { useRef, useState } from "react";
import { submitLead, LeadSubmitError, type LeadResponse } from "@/lib/api";
import {
  ALLOWED_RESUME_EXTENSIONS,
  MAX_RESUME_MB,
  type LeadFormErrors,
  type ResumeMetadata,
  formatFileSize,
  toResumeMetadata,
  validateLeadForm,
} from "@/lib/validation";

const ACCEPT = ALLOWED_RESUME_EXTENSIONS.map((e) => `.${e}`).join(",");

type Status = "idle" | "submitting" | "success" | "error";

export default function LeadForm() {
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [errors, setErrors] = useState<LeadFormErrors>({});
  const [status, setStatus] = useState<Status>("idle");
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [result, setResult] = useState<LeadResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const resume: ResumeMetadata | null = resumeFile
    ? toResumeMetadata(resumeFile)
    : null;

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    setResumeFile(e.target.files?.[0] ?? null);
    setStatus("idle");
    setSubmitError(null);
  }

  function clearFile() {
    setResumeFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function resetForm() {
    setFirstName("");
    setLastName("");
    setEmail("");
    clearFile();
    setErrors({});
    setStatus("idle");
    setSubmitError(null);
    setResult(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitError(null);

    const nextErrors = validateLeadForm({ firstName, lastName, email, resume });
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0 || !resumeFile) {
      setStatus("error");
      return;
    }

    setStatus("submitting");
    try {
      const lead = await submitLead({
        firstName,
        lastName,
        email,
        resume: resumeFile,
      });
      setResult(lead);
      setStatus("success");
    } catch (err) {
      const message =
        err instanceof LeadSubmitError
          ? err.message
          : "Something went wrong. Please try again.";
      setSubmitError(message);
      setStatus("error");
    }
  }

  if (status === "success" && result) {
    return (
      <div
        role="status"
        className="rounded-lg border border-emerald-300 bg-emerald-50 p-5 text-sm text-emerald-900"
      >
        <p className="text-base font-semibold">Application received</p>
        <p className="mt-1">
          Thanks, {result.first_name}. We&apos;ve saved your details and
          resume, and we&apos;ll be in touch at {result.email}.
        </p>
        <button
          type="button"
          onClick={resetForm}
          className="mt-4 rounded-lg border border-emerald-300 bg-white px-3 py-2 text-sm font-medium text-emerald-800 hover:bg-emerald-100"
        >
          Submit another application
        </button>
      </div>
    );
  }

  const submitting = status === "submitting";

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-5">
      <Field
        id="firstName"
        label="First name"
        value={firstName}
        onChange={setFirstName}
        error={errors.firstName}
        autoComplete="given-name"
        disabled={submitting}
      />
      <Field
        id="lastName"
        label="Last name"
        value={lastName}
        onChange={setLastName}
        error={errors.lastName}
        autoComplete="family-name"
        disabled={submitting}
      />
      <Field
        id="email"
        label="Email"
        type="email"
        value={email}
        onChange={setEmail}
        error={errors.email}
        autoComplete="email"
        disabled={submitting}
      />

      <div>
        <label
          htmlFor="resume"
          className="mb-1.5 block text-sm font-medium text-gray-800"
        >
          Resume / CV
        </label>
        <input
          ref={fileInputRef}
          id="resume"
          name="resume"
          type="file"
          accept={ACCEPT}
          onChange={handleFileChange}
          disabled={submitting}
          aria-invalid={errors.resume ? "true" : undefined}
          aria-describedby={errors.resume ? "resume-error" : "resume-hint"}
          className="block w-full cursor-pointer rounded-lg border border-gray-300 bg-white text-sm text-gray-700 file:mr-4 file:cursor-pointer file:border-0 file:bg-gray-100 file:px-4 file:py-2.5 file:text-sm file:font-medium file:text-gray-700 hover:file:bg-gray-200 disabled:opacity-60"
        />
        <p id="resume-hint" className="mt-1.5 text-xs text-gray-500">
          Accepted: {ALLOWED_RESUME_EXTENSIONS.join(", ")} · Max {MAX_RESUME_MB}{" "}
          MB
        </p>

        {resume && (
          <div className="mt-3 rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate font-medium text-gray-900">
                  {resume.filename}
                </p>
                <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs text-gray-600">
                  <dt className="text-gray-400">Size</dt>
                  <dd>{formatFileSize(resume.sizeBytes)}</dd>
                  <dt className="text-gray-400">Type</dt>
                  <dd>{resume.contentType || "unknown"}</dd>
                  <dt className="text-gray-400">Extension</dt>
                  <dd>.{resume.extension || "—"}</dd>
                </dl>
              </div>
              <button
                type="button"
                onClick={clearFile}
                disabled={submitting}
                className="shrink-0 text-xs font-medium text-gray-500 underline hover:text-gray-800 disabled:opacity-60"
              >
                Remove
              </button>
            </div>
          </div>
        )}

        {errors.resume && (
          <p id="resume-error" className="mt-1.5 text-sm text-red-600">
            {errors.resume}
          </p>
        )}
      </div>

      <button
        type="submit"
        disabled={submitting}
        className="w-full rounded-lg bg-gray-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-900 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {submitting ? "Submitting…" : "Submit"}
      </button>

      {submitError && (
        <div
          role="alert"
          className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-800"
        >
          {submitError}
        </div>
      )}
    </form>
  );
}

interface FieldProps {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  type?: string;
  autoComplete?: string;
  disabled?: boolean;
}

function Field({
  id,
  label,
  value,
  onChange,
  error,
  type = "text",
  autoComplete,
  disabled,
}: FieldProps) {
  return (
    <div>
      <label
        htmlFor={id}
        className="mb-1.5 block text-sm font-medium text-gray-800"
      >
        {label}
      </label>
      <input
        id={id}
        name={id}
        type={type}
        value={value}
        autoComplete={autoComplete}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={error ? "true" : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
        className={`block w-full rounded-lg border bg-white px-3 py-2.5 text-sm text-gray-900 shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-1 disabled:opacity-60 ${
          error
            ? "border-red-400 focus:ring-red-400"
            : "border-gray-300 focus:ring-gray-900"
        }`}
      />
      {error && (
        <p id={`${id}-error`} className="mt-1.5 text-sm text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}
