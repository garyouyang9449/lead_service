import { describe, expect, it } from "vitest";
import {
  MAX_RESUME_BYTES,
  type ResumeMetadata,
  isLeadFormValid,
  validateEmail,
  validateFirstName,
  validateLastName,
  validateLeadForm,
  validateResume,
} from "./validation";

function pdf(overrides: Partial<ResumeMetadata> = {}): ResumeMetadata {
  return {
    filename: "resume.pdf",
    sizeBytes: 1024,
    contentType: "application/pdf",
    extension: "pdf",
    ...overrides,
  };
}

describe("field validators", () => {
  it("requires first name", () => {
    expect(validateFirstName("")).toBeDefined();
    expect(validateFirstName("  ")).toBeDefined();
    expect(validateFirstName("Ada")).toBeUndefined();
  });

  it("requires last name", () => {
    expect(validateLastName("")).toBeDefined();
    expect(validateLastName("Lovelace")).toBeUndefined();
  });

  it("validates email format", () => {
    expect(validateEmail("")).toBeDefined();
    expect(validateEmail("not-an-email")).toBeDefined();
    expect(validateEmail("ada@example.com")).toBeUndefined();
  });
});

describe("validateResume", () => {
  it("requires a file", () => {
    expect(validateResume(null)).toBeDefined();
  });

  it("accepts allowed types", () => {
    expect(validateResume(pdf())).toBeUndefined();
    expect(
      validateResume(pdf({ filename: "cv.docx", extension: "docx", contentType: "" })),
    ).toBeUndefined();
  });

  it("rejects disallowed extensions", () => {
    expect(
      validateResume(pdf({ filename: "evil.exe", extension: "exe", contentType: "" })),
    ).toBeDefined();
  });

  it("rejects oversized files", () => {
    expect(validateResume(pdf({ sizeBytes: MAX_RESUME_BYTES + 1 }))).toBeDefined();
  });
});

describe("validateLeadForm", () => {
  it("passes a fully valid form", () => {
    const values = {
      firstName: "Ada",
      lastName: "Lovelace",
      email: "ada@example.com",
      resume: pdf(),
    };
    expect(validateLeadForm(values)).toEqual({});
    expect(isLeadFormValid(values)).toBe(true);
  });

  it("collects all errors for an empty form", () => {
    const errors = validateLeadForm({
      firstName: "",
      lastName: "",
      email: "",
      resume: null,
    });
    expect(errors.firstName).toBeDefined();
    expect(errors.lastName).toBeDefined();
    expect(errors.email).toBeDefined();
    expect(errors.resume).toBeDefined();
  });
});
