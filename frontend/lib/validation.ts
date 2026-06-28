// Pure, framework-agnostic validation logic for the public lead form.
// Kept free of React so it can be unit-tested in isolation.

export const ALLOWED_RESUME_EXTENSIONS = ["pdf", "doc", "docx"] as const;

export const ALLOWED_RESUME_MIME_TYPES = [
  "application/pdf",
  "application/msword",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
] as const;

// Keep in sync with backend MAX_RESUME_MB (defaults to 5 MB).
export const MAX_RESUME_MB = 5;
export const MAX_RESUME_BYTES = MAX_RESUME_MB * 1024 * 1024;

// Metadata extracted from a selected file for display + validation.
export interface ResumeMetadata {
  filename: string;
  sizeBytes: number;
  contentType: string;
  extension: string;
}

export interface LeadFormValues {
  firstName: string;
  lastName: string;
  email: string;
  resume: ResumeMetadata | null;
}

export type LeadFormField = keyof LeadFormValues;

export type LeadFormErrors = Partial<Record<LeadFormField, string>>;

function getExtension(filename: string): string {
  const idx = filename.lastIndexOf(".");
  if (idx === -1 || idx === filename.length - 1) return "";
  return filename.slice(idx + 1).toLowerCase();
}

export function toResumeMetadata(file: File): ResumeMetadata {
  return {
    filename: file.name,
    sizeBytes: file.size,
    contentType: file.type,
    extension: getExtension(file.name),
  };
}

// Basic, pragmatic email check. The backend performs authoritative validation.
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateFirstName(value: string): string | undefined {
  if (!value.trim()) return "First name is required.";
  return undefined;
}

export function validateLastName(value: string): string | undefined {
  if (!value.trim()) return "Last name is required.";
  return undefined;
}

export function validateEmail(value: string): string | undefined {
  if (!value.trim()) return "Email is required.";
  if (!EMAIL_RE.test(value.trim())) return "Enter a valid email address.";
  return undefined;
}

export function validateResume(
  resume: ResumeMetadata | null,
): string | undefined {
  if (!resume) return "A resume/CV file is required.";

  const extOk = (ALLOWED_RESUME_EXTENSIONS as readonly string[]).includes(
    resume.extension,
  );
  const typeOk =
    resume.contentType === "" ||
    (ALLOWED_RESUME_MIME_TYPES as readonly string[]).includes(
      resume.contentType,
    );

  if (!extOk || !typeOk) {
    return `Unsupported file type. Allowed: ${ALLOWED_RESUME_EXTENSIONS.join(", ")}.`;
  }
  if (resume.sizeBytes > MAX_RESUME_BYTES) {
    return `File is too large. Maximum size is ${MAX_RESUME_MB} MB.`;
  }
  return undefined;
}

export function validateLeadForm(values: LeadFormValues): LeadFormErrors {
  const errors: LeadFormErrors = {};
  const firstName = validateFirstName(values.firstName);
  if (firstName) errors.firstName = firstName;
  const lastName = validateLastName(values.lastName);
  if (lastName) errors.lastName = lastName;
  const email = validateEmail(values.email);
  if (email) errors.email = email;
  const resume = validateResume(values.resume);
  if (resume) errors.resume = resume;
  return errors;
}

export function isLeadFormValid(values: LeadFormValues): boolean {
  return Object.keys(validateLeadForm(values)).length === 0;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}
