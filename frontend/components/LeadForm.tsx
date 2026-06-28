"use client";

import { useRef, useState } from "react";
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

export default function LeadForm() {
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [resume, setResume] = useState<ResumeMetadata | null>(null);
  const [errors, setErrors] = useState<LeadFormErrors>({});
  const [submitted, setSubmitted] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    setResume(file ? toResumeMetadata(file) : null);
    setSubmitted(false);
  }

  function clearFile() {
    setResume(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const values = { firstName, lastName, email, resume };
    const nextErrors = validateLeadForm(values);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length === 0) {
      // Backend is intentionally not wired up yet.
      setSubmitted(true);
    } else {
      setSubmitted(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-5">
      <Field
        id="firstName"
        label="First name"
        value={firstName}
        onChange={setFirstName}
        error={errors.firstName}
        autoComplete="given-name"
      />
      <Field
        id="lastName"
        label="Last name"
        value={lastName}
        onChange={setLastName}
        error={errors.lastName}
        autoComplete="family-name"
      />
      <Field
        id="email"
        label="Email"
        type="email"
        value={email}
        onChange={setEmail}
        error={errors.email}
        autoComplete="email"
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
          aria-invalid={errors.resume ? "true" : undefined}
          aria-describedby={errors.resume ? "resume-error" : "resume-hint"}
          className="block w-full cursor-pointer rounded-lg border border-gray-300 bg-white text-sm text-gray-700 file:mr-4 file:cursor-pointer file:border-0 file:bg-gray-100 file:px-4 file:py-2.5 file:text-sm file:font-medium file:text-gray-700 hover:file:bg-gray-200"
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
                className="shrink-0 text-xs font-medium text-gray-500 underline hover:text-gray-800"
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
        className="w-full rounded-lg bg-gray-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-900 focus:ring-offset-2"
      >
        Submit application
      </button>

      {submitted && (
        <div
          role="status"
          className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900"
        >
          <p className="font-semibold">Form is valid.</p>
          <p className="mt-1">
            Backend integration is not wired up yet, so nothing was sent. This
            confirms the form and validation are working.
          </p>
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
}

function Field({
  id,
  label,
  value,
  onChange,
  error,
  type = "text",
  autoComplete,
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
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={error ? "true" : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
        className={`block w-full rounded-lg border bg-white px-3 py-2.5 text-sm text-gray-900 shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-1 ${
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
