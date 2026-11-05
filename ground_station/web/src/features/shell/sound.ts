let ctx: AudioContext | null = null;

/** Short alert tones: person two-tone 880 -> 660 Hz, fire/smoke 520 Hz. Silent if audio is unavailable. */
export function playTones(freqs: number[]): void {
  try {
    const AC = (window as any).AudioContext || (window as any).webkitAudioContext;
    if (!AC) return;
    ctx = ctx ?? new AC();
    const c = ctx!;
    if (c.state === "suspended") c.resume();
    const t0 = c.currentTime;
    freqs.forEach((f, i) => {
      const o = c.createOscillator(), g = c.createGain();
      o.type = "sine"; o.frequency.value = f;
      const s = t0 + i * 0.18;
      g.gain.setValueAtTime(0.0001, s);
      g.gain.exponentialRampToValueAtTime(0.25, s + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, s + 0.16);
      o.connect(g).connect(c.destination);
      o.start(s); o.stop(s + 0.17);
    });
  } catch { /* audio blocked */ }
}

export const TONES = { person: [880, 660], fire: [520], smoke: [520] } as const;
