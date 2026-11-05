import * as TG from "@radix-ui/react-toggle-group";
import { cn } from "./cn";

/** Single-select segmented control (Radix ToggleGroup). */
export function Segmented<T extends string>({ value, onChange, options, label, className }: {
  value: T; onChange(v: T): void; options: { value: T; label: string }[]; label: string; className?: string;
}) {
  return (
    <TG.Root type="single" value={value} aria-label={label}
      onValueChange={(v) => v && onChange(v as T)}
      className={cn("inline-flex rounded-lg border border-line bg-surface-2 p-0.5", className)}>
      {options.map((o) => (
        <TG.Item key={o.value} value={o.value}
          className="rounded-md px-2.5 py-1 text-xs font-semibold text-text-2 data-[state=on]:bg-surface-3 data-[state=on]:text-text">
          {o.label}
        </TG.Item>
      ))}
    </TG.Root>
  );
}

/** Multi-select toggle chips. */
export function MultiToggle<T extends string>({ value, onChange, options, label }: {
  value: T[]; onChange(v: T[]): void; options: { value: T; label: string; className?: string }[]; label: string;
}) {
  return (
    <TG.Root type="multiple" value={value} aria-label={label} onValueChange={(v) => onChange(v as T[])}
      className="inline-flex rounded-lg border border-line bg-surface-2 p-0.5">
      {options.map((o) => (
        <TG.Item key={o.value} value={o.value}
          className={cn("flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold text-muted line-through",
            "data-[state=on]:bg-surface-3 data-[state=on]:text-text data-[state=on]:no-underline")}>
          <span aria-hidden className={cn("h-2 w-2 rounded-sm", o.className)} />{o.label}
        </TG.Item>
      ))}
    </TG.Root>
  );
}
