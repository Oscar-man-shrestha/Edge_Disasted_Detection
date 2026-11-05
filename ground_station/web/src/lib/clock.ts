/** Server-time clock: every age/timer in the UI uses the station's clock, never the browser's. */
export interface Clock {
  /** Record that the server's time was `serverTimeS` at local time `localMs` (default: now). */
  sync(serverTimeS: number, localMs?: number): void;
  /** Current server time in seconds. */
  now(): number;
}

export function createClock(localNowMs: () => number = () => Date.now()): Clock {
  let offsetS = 0; // server - local, seconds
  return {
    sync(serverTimeS, localMs = localNowMs()) {
      if (Number.isFinite(serverTimeS)) offsetS = serverTimeS - localMs / 1000;
    },
    now() {
      return localNowMs() / 1000 + offsetS;
    },
  };
}
