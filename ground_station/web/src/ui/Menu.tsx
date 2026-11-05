import * as M from "@radix-ui/react-dropdown-menu";
import type { ReactNode } from "react";
import { cn } from "./cn";

export const MenuRoot = M.Root;
export const MenuTrigger = M.Trigger;

export function MenuContent({ children, align = "end" }: { children: ReactNode; align?: "start" | "end" }) {
  return (
    <M.Portal>
      <M.Content align={align} sideOffset={6}
        className="z-[2500] min-w-[200px] rounded-xl border border-line bg-surface-2 p-1 text-sm text-text shadow-panel">
        {children}
      </M.Content>
    </M.Portal>
  );
}

export function MenuItem({ children, onSelect, asChild, className }: {
  children: ReactNode; onSelect?: () => void; asChild?: boolean; className?: string;
}) {
  return (
    <M.Item asChild={asChild} onSelect={onSelect}
      className={cn("flex cursor-pointer select-none items-center gap-2 rounded-lg px-2.5 py-2 outline-none data-[highlighted]:bg-surface-3", className)}>
      {children}
    </M.Item>
  );
}

export const MenuLabel = ({ children }: { children: ReactNode }) => (
  <M.Label className="px-2.5 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-muted">{children}</M.Label>
);
export const MenuSeparator = () => <M.Separator className="my-1 h-px bg-line" />;
