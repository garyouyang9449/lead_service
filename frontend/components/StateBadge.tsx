import type { LeadState } from "@/lib/api";

const STYLES: Record<LeadState, string> = {
  PENDING: "border-amber-300 bg-amber-50 text-amber-800",
  REACHED_OUT: "border-emerald-300 bg-emerald-50 text-emerald-800",
};

const LABELS: Record<LeadState, string> = {
  PENDING: "Pending",
  REACHED_OUT: "Reached out",
};

export default function StateBadge({ state }: { state: LeadState }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${STYLES[state]}`}
    >
      {LABELS[state]}
    </span>
  );
}
