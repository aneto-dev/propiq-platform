import type { DealStatus } from "@/lib/types/deal";

/**
 * Visual status badge for all deal lifecycle states.
 *
 * DRAFT            — neutral gray (no analysis yet)
 * ANALYSED         — blue (analysis complete, considering offer)
 * OFFER_SUBMITTED  — yellow (active pursuit)
 * PURCHASED        — purple (property acquired)
 * HELD             — green (in portfolio, generating rent)
 * EXITED           — teal (sold / deal exited)
 * ARCHIVED         — amber (no longer active)
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Phase 10 Feature 1.
 */

const STYLES: Record<DealStatus, string> = {
  DRAFT:           "bg-gray-100 text-gray-600",
  ANALYSED:        "bg-blue-100 text-blue-700",
  OFFER_SUBMITTED: "bg-yellow-100 text-yellow-800",
  PURCHASED:       "bg-purple-100 text-purple-700",
  HELD:            "bg-green-100 text-green-700",
  EXITED:          "bg-teal-100 text-teal-700",
  ARCHIVED:        "bg-amber-100 text-amber-700",
};

const LABELS: Record<DealStatus, string> = {
  DRAFT:           "Draft",
  ANALYSED:        "Analysed",
  OFFER_SUBMITTED: "Offer submitted",
  PURCHASED:       "Purchased",
  HELD:            "Held",
  EXITED:          "Exited",
  ARCHIVED:        "Archived",
};

interface DealStatusBadgeProps {
  status: DealStatus;
}

export function DealStatusBadge({ status }: DealStatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${STYLES[status]}`}
    >
      {LABELS[status]}
    </span>
  );
}
