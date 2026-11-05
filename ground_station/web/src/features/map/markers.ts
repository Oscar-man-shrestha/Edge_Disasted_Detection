import type { Alert, AlertType } from "../../lib/types";

const LETTER: Record<AlertType, string> = { person: "P", fire: "F", smoke: "S" };

export function droneElement(): HTMLDivElement {
  const el = document.createElement("div");
  el.className = "gs-drone";
  el.setAttribute("aria-label", "Drone");
  el.innerHTML =
    '<svg width="34" height="34" viewBox="0 0 34 34" aria-hidden="true">' +
    '<circle cx="17" cy="17" r="15" fill="rgb(57 135 229 / 0.18)" stroke="rgb(57 135 229 / 0.55)" stroke-width="1.5"/>' +
    '<path d="M17 4 L27 28 L17 22 L7 28 Z" fill="#e8ebf1" stroke="#0d1016" stroke-width="2" stroke-linejoin="round"/></svg>';
  return el;
}

/** Alert marker: coloured disc with a type letter (colour is never the only cue). */
export function alertElement(a: Alert, selected: boolean, onClick: (id: number) => void): HTMLButtonElement {
  const el = document.createElement("button");
  el.type = "button";
  el.className = `gs-amark gs-amark-${a.type} gs-amark-${a.status}${selected ? " gs-amark-selected" : ""}`;
  el.textContent = LETTER[a.type];
  el.setAttribute("aria-label", `${a.type} alert ${a.id}, ${Math.round(a.conf * 100)} percent, ${a.status}`);
  el.addEventListener("click", (e) => { e.stopPropagation(); onClick(a.id); });
  return el;
}

export function clusterElement(counts: Record<AlertType, number>, total: number, onClick: () => void): HTMLButtonElement {
  const el = document.createElement("button");
  el.type = "button";
  el.className = "gs-cluster";
  el.setAttribute("aria-label", `${total} alerts here: ${counts.person} person, ${counts.fire} fire, ${counts.smoke} smoke`);
  const parts = (["person", "fire", "smoke"] as AlertType[]).filter((t) => counts[t] > 0)
    .map((t) => `<span class="gs-cluster-${t}">${LETTER[t]}${counts[t]}</span>`).join("");
  el.innerHTML = `<b>${total}</b><span class="gs-cluster-parts">${parts}</span>`;
  el.addEventListener("click", (e) => { e.stopPropagation(); onClick(); });
  return el;
}
