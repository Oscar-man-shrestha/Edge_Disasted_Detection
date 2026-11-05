import { Fragment } from "react";
import { useOverlays } from "../../store/ui";
import { DialogContent, DialogRoot } from "../../ui/Dialog";
import { Kbd } from "../../ui/Panel";

export const SHORTCUTS: [string, string][] = [
  ["⌘/Ctrl K", "Command palette"], ["A", "Acknowledge selected alert"], ["R", "Resolve selected alert"],
  ["F", "Follow drone"], ["3", "Toggle 3D map"], ["N", "North up"],
  ["Space", "Play / pause (Replay)"], ["← →", "Step 10 s (Replay)"], ["?", "This help"],
];

export function ShortcutHelp() {
  const open = useOverlays((s) => s.help);
  const set = useOverlays((s) => s.set);
  return (
    <DialogRoot open={open} onOpenChange={(o) => set({ help: o })}>
      <DialogContent title="Keyboard shortcuts" description="Shortcuts are ignored while you type in a field.">
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
          {SHORTCUTS.map(([k, d]) => (<Fragment key={k}><dt><Kbd>{k}</Kbd></dt><dd className="text-text-2">{d}</dd></Fragment>))}
        </dl>
      </DialogContent>
    </DialogRoot>
  );
}
