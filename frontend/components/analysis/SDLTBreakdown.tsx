import type { SnapshotIntermediates } from "@/lib/types/snapshot";

/**
 * SDLT band-by-band breakdown table.
 *
 * Renders sdlt_band_breakdown from SnapshotIntermediates — an ordered array
 * of each band applied, the taxable amount in that band, the rate, and the
 * tax computed. Surcharge and total lines are shown beneath.
 *
 * Requires SnapshotFull (GET /api/v1/snapshots/{id}/full); sdlt_band_breakdown
 * is not present in the display-level summary response.
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.6.
 * CALCULATION_SPEC.md F-13 — SDLT band calculation.
 * SERVICE_ARCHITECTURE.md Part 10 — renders what the API returns.
 */

interface SDLTBreakdownProps {
  intermediates: SnapshotIntermediates;
}

function gbp(value: string): string {
  const num = parseFloat(value);
  return `£${Math.abs(num).toLocaleString("en-GB", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function SDLTBreakdown({ intermediates }: SDLTBreakdownProps) {
  const { sdlt_band_breakdown, sdlt_base_gbp, sdlt_surcharge_gbp, sdlt_surcharge_rate_applied, total_sdlt_gbp } =
    intermediates;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200">
            <th className="text-left py-2 pr-4 text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Band
            </th>
            <th className="text-right py-2 pr-4 text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Rate
            </th>
            <th className="text-right py-2 pr-4 text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Taxable in band
            </th>
            <th className="text-right py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Tax
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {sdlt_band_breakdown.map((band, i) => (
            <tr key={i} className="text-gray-700">
              <td className="py-2 pr-4 tabular-nums">
                {gbp(band.band_lower)}
                {band.band_upper !== null ? ` – ${gbp(band.band_upper)}` : "+"}
              </td>
              <td className="py-2 pr-4 text-right tabular-nums">
                {band.rate}%
              </td>
              <td className="py-2 pr-4 text-right tabular-nums">
                {gbp(band.taxable_in_band)}
              </td>
              <td className="py-2 text-right tabular-nums">
                {gbp(band.tax_in_band)}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot className="border-t border-gray-200">
          <tr className="text-gray-700">
            <td colSpan={3} className="py-2 pr-4">
              SDLT base
            </td>
            <td className="py-2 text-right tabular-nums font-medium">
              {gbp(sdlt_base_gbp)}
            </td>
          </tr>
          {parseFloat(sdlt_surcharge_gbp) > 0 && (
            <tr className="text-gray-700">
              <td colSpan={3} className="py-2 pr-4">
                Additional dwelling surcharge ({sdlt_surcharge_rate_applied}%)
              </td>
              <td className="py-2 text-right tabular-nums font-medium">
                {gbp(sdlt_surcharge_gbp)}
              </td>
            </tr>
          )}
          <tr className="border-t border-gray-300 font-semibold text-gray-900">
            <td colSpan={3} className="py-2 pr-4">
              Total SDLT
            </td>
            <td className="py-2 text-right tabular-nums">
              {gbp(total_sdlt_gbp)}
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
