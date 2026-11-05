import type { Map as MLMap } from "maplibre-gl";
import { Crosshair, Layers, Maximize2, Minus, Navigation, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { usePrefs } from "../../store/ui";
import { Button } from "../../ui/Button";
import { MenuContent, MenuItem, MenuLabel, MenuRoot, MenuTrigger } from "../../ui/Menu";
import { Tip } from "../../ui/Tooltip";
import { cn } from "../../ui/cn";

export interface LayerToggles { trail: boolean; alerts: boolean; terrain: boolean; dim: boolean }

export function MapControls({ map, layers, onLayers, onFit, live }: {
  map: MLMap; layers: LayerToggles; onLayers(l: LayerToggles): void; onFit(): void; live: boolean;
}) {
  const prefs = usePrefs((s) => s.prefs);
  const setPrefs = usePrefs((s) => s.set);
  const [bearing, setBearing] = useState(map.getBearing());
  useEffect(() => {
    const h = () => setBearing(map.getBearing());
    map.on("rotate", h);
    return () => { map.off("rotate", h); };
  }, [map]);
  const btn = "bg-surface/95 shadow-panel backdrop-blur";
  const on = "!border-accent !text-accent";
  const toggle = (k: keyof LayerToggles) => onLayers({ ...layers, [k]: !layers[k] });

  return (
    <div className="absolute right-3 top-3 z-10 flex flex-col gap-1.5">
      <div className="flex flex-col overflow-hidden rounded-lg border border-line">
        <button type="button" aria-label="Zoom in" onClick={() => map.zoomIn()} className={cn("grid h-8 w-8 place-items-center hover:bg-surface-2", btn)}><Plus size={16} /></button>
        <button type="button" aria-label="Zoom out" onClick={() => map.zoomOut()} className={cn("grid h-8 w-8 place-items-center border-t border-line hover:bg-surface-2", btn)}><Minus size={16} /></button>
      </div>
      <Tip label="North up (N)">
        <Button size="icon" aria-label="North up" className={btn} onClick={() => map.easeTo({ bearing: 0, duration: 500 })}>
          <Navigation size={16} style={{ transform: `rotate(${-bearing}deg)` }} />
        </Button>
      </Tip>
      <Tip label="2D / 3D (3)">
        <Button size="icon" aria-pressed={prefs.map3d} aria-label="Toggle 3D" className={cn(btn, "font-mono text-xs font-bold", prefs.map3d && on)}
          onClick={() => setPrefs({ map3d: !prefs.map3d })}>{prefs.map3d ? "3D" : "2D"}</Button>
      </Tip>
      {live && (
        <>
          <Tip label="Follow drone (F)">
            <Button size="icon" aria-pressed={prefs.follow} aria-label="Follow drone" className={cn(btn, prefs.follow && on)}
              onClick={() => setPrefs({ follow: !prefs.follow })}><Crosshair size={16} /></Button>
          </Tip>
          <Tip label="Heading up">
            <Button size="icon" aria-pressed={prefs.headingUp} aria-label="Heading up" className={cn(btn, "text-[10px] font-bold", prefs.headingUp && on)}
              onClick={() => setPrefs({ headingUp: !prefs.headingUp })}>HDG</Button>
          </Tip>
        </>
      )}
      <Tip label="Fit all">
        <Button size="icon" aria-label="Fit all" className={btn} onClick={onFit}><Maximize2 size={16} /></Button>
      </Tip>
      <MenuRoot>
        <MenuTrigger asChild>
          <Button size="icon" aria-label="Map layers" className={btn}><Layers size={16} /></Button>
        </MenuTrigger>
        <MenuContent>
          <MenuLabel>Layers</MenuLabel>
          {([["trail", "Flight trail"], ["alerts", "Alert markers"], ["terrain", "3D terrain (when 3D)"], ["dim", "Dim basemap"]] as const).map(([k, label]) => (
            <MenuItem key={k} onSelect={() => toggle(k)}>
              <span aria-hidden className={cn("grid h-4 w-4 place-items-center rounded border text-[10px]", layers[k] ? "border-accent bg-accent text-white" : "border-line")}>
                {layers[k] ? "✓" : ""}
              </span>
              {label}
            </MenuItem>
          ))}
        </MenuContent>
      </MenuRoot>
    </div>
  );
}
