import { toast } from "sonner";
import { updateAlert } from "../../lib/api";
import type { Alert, AlertStatus } from "../../lib/types";
import { useLive } from "../../store/live";

/** Server is the source of truth: apply only the server's reply (no optimistic state). */
export async function setAlertStatus(a: Alert, status: AlertStatus): Promise<boolean> {
  try {
    const updated = await updateAlert(a.id, { status });
    useLive.getState().applyEvent("alert_update", { alert: updated });
    return true;
  } catch (e) {
    toast.error(`Update failed: ${(e as Error).message}`);
    return false;
  }
}

export async function saveAlertNote(a: Alert, note: string): Promise<boolean> {
  try {
    const updated = await updateAlert(a.id, { note });
    useLive.getState().applyEvent("alert_update", { alert: updated });
    toast.success("Note saved");
    return true;
  } catch (e) {
    toast.error(`Update failed: ${(e as Error).message}`);
    return false;
  }
}
