import type { DealStatus } from "@/lib/types/deal";

/**
 * Visual status badge for DRAFT / ANALYSED / ARCHIVED deal states.
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.5.
 */

const STYLES: Record<DealStatus, string> = {
  DRAFT: "bg-gray-100 text-gray-600",
  ANALYSED: "bg-blue-100 text-blue-700",
  ARCHIVED: "bg-amber-100 text-amber-700",
};

const LABELS: Record<DealStatus, string> = {
  DRAFT: "Draft",
  ANALYSED: "Analysed",
  ARCHIVED: "Archived",
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
