import type { Alert, AlertType } from "../../lib/types";

const LETTER: Record<AlertType, string> = { person: "P", fire: "F", smoke: "S" };

/** Shape per type, so colour is never the only cue. Constants only (no network data in innerHTML). */
const ICON: Record<AlertType, string> = {
  fire: '<path d="M12 2c1 3.2-1.6 4.6-1.6 7.4 0 1.4.9 2.4 2 2.4s1.9-1 1.9-2.3c2.3 1.6 3.7 4 3.7 6.5A6 6 0 0 1 12 22a6 6 0 0 1-6-6c0-4.6 3.6-6.8 6-14Z"/>',
  person: '<circle cx="12" cy="6" r="3.2"/><path d="M6 21v-5.5A4.5 4.5 0 0 1 10.5 11h3a4.5 4.5 0 0 1 4.5 4.5V21Z"/>',
  smoke: '<g fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M7 21c-2.2-2.6 2.2-4.4 0-7s2.2-4.4 0-7"/><path d="M12 21c-2.2-2.6 2.2-4.4 0-7s2.2-4.4 0-7s2.2-3 0-5"/><path d="M17 21c-2.2-2.6 2.2-4.4 0-7s2.2-4.4 0-7"/></g>',
};
const iconSvg = (t: AlertType) =>
  `<svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor" aria-hidden="true">${ICON[t]}</svg>`;

/** Top-down quadcopter: four spinning rotors, a forward camera cone and a scan ring.
 *  The nose points up; the map marker rotates it to the drone's course. Pure SVG + CSS:
 *  everything runs in the browser, nothing extra is asked of the drone. */
export function droneElement(): HTMLDivElement {
  const el = document.createElement("div");
  el.className = "gs-drone";
  el.setAttribute("role", "img");
  el.setAttribute("aria-label", "Drone");
  const rotor = (x: number, y: number, d: string) =>
    `<g transform="translate(${x} ${y})"><circle r="11" class="gs-rotor-disc"/>` +
    `<g class="gs-rotor gs-rotor-${d}"><rect x="-10.5" y="-1.4" width="21" height="2.8" rx="1.4"/>` +
    `<rect x="-1.4" y="-10.5" width="2.8" height="21" rx="1.4" opacity="0.55"/></g>` +
    `<circle r="2.2" class="gs-rotor-hub"/></g>`;
  el.innerHTML =
    '<span class="gs-drone-scan" aria-hidden="true"></span>' +
    '<svg class="gs-drone-fov" viewBox="0 0 120 120" aria-hidden="true"><defs>' +
    '<linearGradient id="gs-fov-g" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="rgb(57 135 229 / 0.45)"/>' +
    '<stop offset="1" stop-color="rgb(57 135 229 / 0)"/></linearGradient></defs>' +
    '<path d="M60 60 L28 4 A64 64 0 0 1 92 4 Z" fill="url(#gs-fov-g)"/></svg>' +
    '<svg class="gs-drone-body" viewBox="0 0 64 64" aria-hidden="true">' +
    '<g class="gs-drone-arms"><path d="M17 17 L47 47 M47 17 L17 47"/></g>' +
    rotor(17, 17, "cw") + rotor(47, 17, "ccw") + rotor(17, 47, "ccw") + rotor(47, 47, "cw") +
    '<rect x="24" y="22" width="16" height="20" rx="6" class="gs-drone-hull"/>' +
    '<path d="M32 14 L37 22 L27 22 Z" class="gs-drone-nose"/>' +
    '<circle cx="32" cy="32" r="3" class="gs-drone-cam"/>' +
    '<circle cx="18" cy="12" r="1.6" class="gs-led gs-led-port"/><circle cx="46" cy="12" r="1.6" class="gs-led gs-led-stbd"/>' +
    "</svg>";
  return el;
}

/** Alert marker: coloured disc with a type letter (colour is never the only cue).
 *  The same element is reused across renders (see updateAlertElement) so clicks and focus survive. */
export function alertElement(a: Alert, selected: boolean, onClick: (id: number) => void): HTMLButtonElement {
  const el = document.createElement("button");
  el.type = "button";
  updateAlertElement(el, a, selected, onClick);
  return el;
}

export function updateAlertElement(el: HTMLElement, a: Alert, selected: boolean, onClick: (id: number) => void): void {
  // Only touch our own gs-amark* classes: MapLibre adds "maplibregl-marker ..." to the same
  // element, and that class is what positions it at its coordinates (overwriting className
  // dropped it, so pins fell back to normal layout and stacked up away from their spot).
  const want = ["gs-amark", `gs-amark-${a.type}`, `gs-amark-${a.status}`, ...(selected ? ["gs-amark-selected"] : [])];
  for (const c of [...el.classList]) if (c.startsWith("gs-amark") && !want.includes(c)) el.classList.remove(c);
  for (const c of want) if (!el.classList.contains(c)) el.classList.add(c);
  if (el.dataset.type !== a.type) { el.dataset.type = a.type; el.innerHTML = iconSvg(a.type); }
  el.setAttribute("aria-label", `${a.type} alert ${a.id}, ${Math.round(a.conf * 100)} percent, ${a.status}`);
  el.onclick = (e) => { e.stopPropagation(); onClick(a.id); };
}

export function clusterElement(counts: Record<AlertType, number>, total: number, onClick: () => void): HTMLButtonElement {
  const el = document.createElement("button");
  el.type = "button";
  el.className = "gs-cluster";
  updateClusterElement(el, counts, total, onClick);
  return el;
}

export function updateClusterElement(el: HTMLElement, counts: Record<AlertType, number>, total: number, onClick: () => void): void {
  el.setAttribute("aria-label", `${total} alerts here: ${counts.person} person, ${counts.fire} fire, ${counts.smoke} smoke`);
  // numbers and constants only (no network strings) in innerHTML
  const parts = (["person", "fire", "smoke"] as AlertType[]).filter((t) => counts[t] > 0)
    .map((t) => `<span class="gs-cluster-${t}" title="${LETTER[t]}">${iconSvg(t)}${Number(counts[t])}</span>`).join("");
  const html = `<b>${Number(total)}</b><span class="gs-cluster-parts">${parts}</span>`;
  if (el.innerHTML !== html) el.innerHTML = html;
  el.onclick = (e) => { e.stopPropagation(); onClick(); };
}

/** True position of a fanned-out group: a dot with a thin leg to each pin. Numbers only in innerHTML. */
export function hubElement(legs: [number, number][]): HTMLDivElement {
  const el = document.createElement("div");
  el.className = "gs-hub";
  el.setAttribute("aria-hidden", "true");
  updateHubElement(el, legs);
  return el;
}

export function updateHubElement(el: HTMLElement, legs: [number, number][]): void {
  const r = Math.max(30, ...legs.map(([x, y]) => Math.ceil(Math.hypot(x, y)) + 2));
  const lines = legs.map(([x, y]) => `<line x1="${r}" y1="${r}" x2="${r + Number(x)}" y2="${r + Number(y)}"/>`).join("");
  const html = `<svg width="${2 * r}" height="${2 * r}" viewBox="0 0 ${2 * r} ${2 * r}">${lines}` +
    `<circle cx="${r}" cy="${r}" r="4"/></svg>`;
  if (el.innerHTML !== html) el.innerHTML = html;
}

/** Searched coordinates: a crosshair target. */
export function targetElement(): HTMLDivElement {
  const el = document.createElement("div");
  el.className = "gs-target";
  el.setAttribute("role", "img");
  el.setAttribute("aria-label", "Searched location");
  el.innerHTML = '<svg viewBox="0 0 48 48" width="48" height="48" aria-hidden="true">' +
    '<circle cx="24" cy="24" r="14"/><circle cx="24" cy="24" r="3" class="gs-target-dot"/>' +
    '<path d="M24 2v10M24 36v10M2 24h10M36 24h10"/></svg>';
  return el;
}
