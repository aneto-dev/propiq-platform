import type { RiskFlag, FlagSeverity } from "@/lib/types/snapshot";

/**
 * Risk flag list — displays triggered flags sorted HIGH → MEDIUM → INFO.
 *
 * Each flag shows its severity badge, code, and the stored message text.
 * The backend does not guarantee sort order; sorting is applied here.
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.6.
 * SERVICE_ARCHITECTURE.md Part 10 — renders API values; no derived logic.
 */

const SEVERITY_ORDER: Record<FlagSeverity, number> = {
  HIGH: 0,
  MEDIUM: 1,
  INFO: 2,
};

const SEVERITY_STYLES: Record<FlagSeverity, { badge: string; row: string }> = {
  HIGH: {
    badge: "bg-red-100 text-red-700",
    row: "border-red-200 bg-red-50",
  },
  MEDIUM: {
    badge: "bg-amber-100 text-amber-700",
    row: "border-amber-200 bg-amber-50",
  },
  INFO: {
    badge: "bg-blue-100 text-blue-700",
    row: "border-blue-200 bg-blue-50",
  },
};

interface RiskFlagListProps {
  flags: RiskFlag[];
}

export function RiskFlagList({ flags }: RiskFlagListProps) {
  if (flags.length === 0) {
    return (
      <p className="text-sm text-gray-500">
        No risk flags triggered for this deal.
      </p>
    );
  }

  const sorted = [...flags].sort(
    (a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity],
  );

  return (
    <ul className="space-y-3">
      {sorted.map((flag) => {
        const styles = SEVERITY_STYLES[flag.severity];
        return (
          <li
            key={flag.code}
            className={`rounded-lg border px-4 py-3 ${styles.row}`}
          >
            <div className="flex items-start gap-3">
              <span
                className={`mt-0.5 inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold shrink-0 ${styles.badge}`}
              >
                {flag.severity}
              </span>
              <p className="text-sm text-gray-800">{flag.message}</p>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
