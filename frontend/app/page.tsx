import LeadForm from "@/components/LeadForm";

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center px-4 py-12">
      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm sm:p-8">
        <header className="mb-6">
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">
            Submit your application
          </h1>
          <p className="mt-1.5 text-sm text-gray-600">
            Tell us who you are and attach your resume or CV. We&apos;ll be in
            touch.
          </p>
        </header>
        <LeadForm />
      </div>
    </main>
  );
}
