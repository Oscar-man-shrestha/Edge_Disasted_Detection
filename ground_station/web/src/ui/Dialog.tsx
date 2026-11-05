import * as D from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "./cn";

export const DialogRoot = D.Root;
export const DialogTrigger = D.Trigger;
export const DialogClose = D.Close;

export function DialogContent({ title, description, children, className, side }: {
  title: string; description?: string; children: ReactNode; className?: string; side?: "right" | "bottom";
}) {
  return (
    <D.Portal>
      <D.Overlay className="fixed inset-0 z-[3000] bg-black/55 backdrop-blur-[2px]" />
      <D.Content
        aria-describedby={description ? undefined : undefined}
        className={cn(
          "fixed z-[3001] border border-line bg-surface text-text shadow-panel focus:outline-none",
          !side && "left-1/2 top-1/2 w-[min(520px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 rounded-2xl p-5",
          side === "right" && "inset-y-0 right-0 w-[min(440px,100vw)] overflow-y-auto p-5",
          side === "bottom" && "inset-x-0 bottom-0 max-h-[85vh] overflow-y-auto rounded-t-2xl p-4",
          className,
        )}
      >
        <div className="mb-3 flex items-start justify-between gap-3">
          <div>
            <D.Title className="text-base font-semibold">{title}</D.Title>
            {description ? <D.Description className="mt-0.5 text-sm text-text-2">{description}</D.Description>
              : <D.Description className="sr-only">{title}</D.Description>}
          </div>
          <D.Close aria-label="Close" className="rounded-md p-1 text-muted hover:bg-surface-2 hover:text-text">
            <X size={16} />
          </D.Close>
        </div>
        {children}
      </D.Content>
    </D.Portal>
  );
}
