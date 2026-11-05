import { useState } from "react";
import type { Alert } from "../../lib/types";
import { Button } from "../../ui/Button";
import { AlertRow } from "./AlertRow";

const PAGE = 200;

export function AlertList({ alerts, selectedId, onSelect }: {
  alerts: Alert[]; selectedId: number | null; onSelect(id: number): void;
}) {
  const [limit, setLimit] = useState(PAGE);
  if (!alerts.length) {
    return <p className="px-4 py-10 text-center text-sm text-muted">No alerts here yet. They appear the moment the drone detects something.</p>;
  }
  return (
    <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-3">
      <ul className="flex flex-col gap-2">
        {alerts.slice(0, limit).map((a) => <AlertRow key={a.id} alert={a} selected={a.id === selectedId} onSelect={onSelect} />)}
      </ul>
      {alerts.length > limit && (
        <Button className="mt-2 w-full" onClick={() => setLimit((l) => l + PAGE)}>
          Show more ({alerts.length - limit} more)
        </Button>
      )}
    </div>
  );
}
