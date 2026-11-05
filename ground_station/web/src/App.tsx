import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect } from "react";
import { getState } from "./lib/api";
import { connect } from "./lib/sse";
import { AppShell } from "./features/shell/AppShell";
import { useLive } from "./store/live";
import { emitNewAlert } from "./store/notify";

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 10_000, retry: 1 } } });

async function resync() {
  try {
    const missed = useLive.getState().hydrate(await getState());
    missed.forEach(emitNewAlert);
  } catch {
    useLive.getState().setConnection("reconnecting");
  }
}

export default function App() {
  useEffect(() => {
    resync();
    return connect({
      onOpen: resync,
      onState: (c) => useLive.getState().setConnection(c),
      onEvent: (name, data) => {
        if (name === "mission") { resync(); queryClient.invalidateQueries(); return; }
        const r = useLive.getState().applyEvent(name, data);
        if (r.notify) emitNewAlert(r.notify);
      },
    });
  }, []);
  return (
    <QueryClientProvider client={queryClient}>
      <AppShell />
    </QueryClientProvider>
  );
}
