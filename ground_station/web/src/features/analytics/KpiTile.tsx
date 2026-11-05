import type { ReactNode } from "react";

export function KpiTile({ label, value, sub, testId }: { label: string; value: ReactNode; sub?: ReactNode; testId?: string }) {
  return (
    <div data-testid={testId} className="rounded-xl border border-line bg-surface p-3 shadow-panel">
      <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">{label}</div>
      <div className="tabular mt-1 font-mono text-2xl font-semibold">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-text-2">{sub}</div>}
    </div>
  );
}
