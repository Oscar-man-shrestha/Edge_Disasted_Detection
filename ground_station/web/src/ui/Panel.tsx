import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "./cn";

export function Panel({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-xl border border-line bg-surface/95 shadow-panel backdrop-blur", className)} {...rest} />;
}

export function PanelHeader({ title, right, className }: { title: ReactNode; right?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex items-center justify-between gap-2 px-3 pt-2.5 pb-1.5", className)}>
      <h2 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">{title}</h2>
      {right}
    </div>
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="rounded border border-line bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-text-2">{children}</kbd>;
}
