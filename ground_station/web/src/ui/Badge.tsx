import type { HTMLAttributes } from "react";
import type { AlertType } from "../lib/types";
import { cn } from "./cn";

export const TYPE_BG: Record<AlertType, string> = { person: "bg-person", fire: "bg-fire", smoke: "bg-smoke" };
export const TYPE_TEXT: Record<AlertType, string> = { person: "text-person", fire: "text-fire", smoke: "text-smoke" };
export const TYPE_BORDER: Record<AlertType, string> = { person: "border-person", fire: "border-fire", smoke: "border-smoke" };
export const LETTER: Record<AlertType, string> = { person: "P", fire: "F", smoke: "S" };

export function TypeBadge({ type, className }: { type: AlertType; className?: string }) {
  return (
    <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide text-white", TYPE_BG[type], className)}>
      {type}
    </span>
  );
}

export function Badge({ className, ...rest }: HTMLAttributes<HTMLSpanElement>) {
  return <span className={cn("inline-flex items-center gap-1 rounded-full border border-line px-2 py-0.5 text-[11px] font-semibold", className)} {...rest} />;
}

const STATUS_STYLE = {
  new: "border-serious text-text",
  acknowledged: "border-warn/60 text-warn",
  resolved: "border-good/60 text-good",
} as const;

export function StatusBadge({ status }: { status: keyof typeof STATUS_STYLE }) {
  return <Badge className={STATUS_STYLE[status]}>{status}</Badge>;
}
