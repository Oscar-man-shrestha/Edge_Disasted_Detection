import { useMemo, useRef } from "react";
import type { TelemetrySample, Timeline } from "../../lib/types";
import { Panel, PanelHeader } from "../../ui/Panel";
import { segments } from "../replay/replay";
import { token, useEChart, type EChartsOption } from "./echarts";
import type { MinuteBucket } from "./metrics";

function palette() {
  return {
    person: token("--gs-person", "#3987e5"), fire: token("--gs-fire", "#d95926"), smoke: token("--gs-smoke", "#199e70"),
    accent: token("--gs-accent", "#3987e5"), text: token("--gs-text-2", "#a9b0bd"), muted: token("--gs-muted", "#7a8293"),
    line: token("--gs-line", "#2a3140"), surface: token("--gs-surface-2", "#1b202b"), good: token("--gs-good", "#0ca30c"),
  };
}

function base(c: ReturnType<typeof palette>, unit: string): EChartsOption {
  return {
    animationDuration: 300, grid: { left: 48, right: 16, top: 28, bottom: 40 },
    textStyle: { color: c.text, fontFamily: "Inter, system-ui, sans-serif" },
    tooltip: { trigger: "axis", axisPointer: { type: "cross", lineStyle: { color: c.muted } },
      backgroundColor: c.surface, borderColor: c.line, textStyle: { color: c.text },
      valueFormatter: (v: unknown) => (typeof v === "number" ? `${v.toFixed(1)} ${unit}` : "—") },
    xAxis: { type: "time", axisLine: { lineStyle: { color: c.line } }, axisLabel: { color: c.muted }, splitLine: { show: false } },
    yAxis: { type: "value", name: unit, nameTextStyle: { color: c.muted }, axisLabel: { color: c.muted },
      splitLine: { lineStyle: { color: c.line, type: "dashed", opacity: 0.6 } } },
    dataZoom: [{ type: "inside" }],
  };
}

function Chart({ title, option, height = 220, testId }: { title: string; option: EChartsOption; height?: number; testId: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEChart(ref, option);
  return (
    <Panel>
      <PanelHeader title={title} />
      <div ref={ref} data-testid={testId} role="img" aria-label={`${title} chart`} style={{ height }} className="px-1 pb-2" />
    </Panel>
  );
}

const series = (rows: TelemetrySample[], f: (s: TelemetrySample) => number | null) =>
  rows.map((s) => [s.t * 1000, f(s)] as [number, number | null]);

export function DetectionsChart({ buckets, start }: { buckets: MinuteBucket[]; start: number }) {
  const option = useMemo(() => {
    const c = palette();
    const o = base(c, "alerts") as any;
    o.xAxis = { type: "category", data: buckets.map((b) => `+${b.minute}m`), axisLabel: { color: c.muted }, axisLine: { lineStyle: { color: c.line } } };
    o.legend = { top: 0, right: 8, textStyle: { color: c.text }, itemWidth: 10, itemHeight: 10 };
    o.tooltip.axisPointer = { type: "shadow" };
    o.tooltip.valueFormatter = (v: unknown) => `${v}`;
    o.series = (["person", "fire", "smoke"] as const).map((t) => ({
      name: t, type: "bar", stack: "alerts", barMaxWidth: 28, itemStyle: { color: c[t], borderRadius: [2, 2, 0, 0] },
      data: buckets.map((b) => b[t]),
    }));
    o.dataZoom = buckets.length > 30 ? [{ type: "inside" }] : [];
    void start;
    return o as EChartsOption;
  }, [buckets, start]);
  return <Chart title="Detections per minute" option={option} testId="chart-detections" />;
}

export function PowerChart({ rows }: { rows: TelemetrySample[] }) {
  const option = useMemo(() => {
    const c = palette();
    return { ...base(c, "W"), series: [{ name: "Board power", type: "line", showSymbol: false, smooth: true,
      lineStyle: { width: 2, color: c.accent }, itemStyle: { color: c.accent },
      areaStyle: { color: c.accent, opacity: 0.12 }, data: series(rows, (s) => (s.power_mw == null ? null : s.power_mw / 1000)) }] } as EChartsOption;
  }, [rows]);
  return <Chart title="Board power" option={option} testId="chart-power" />;
}

export function TemperatureChart({ rows }: { rows: TelemetrySample[] }) {
  const option = useMemo(() => {
    const c = palette();
    return { ...base(c, "°C"), legend: { top: 0, right: 8, textStyle: { color: c.text } },
      series: [
        { name: "CPU", type: "line", showSymbol: false, lineStyle: { width: 2, color: c.person }, itemStyle: { color: c.person }, data: series(rows, (s) => s.cpu_temp_c) },
        { name: "GPU", type: "line", showSymbol: false, lineStyle: { width: 2, color: c.fire }, itemStyle: { color: c.fire }, data: series(rows, (s) => s.gpu_temp_c) },
      ] } as EChartsOption;
  }, [rows]);
  return <Chart title="Temperatures" option={option} testId="chart-temps" />;
}

export function FpsChart({ rows }: { rows: TelemetrySample[] }) {
  const option = useMemo(() => {
    const c = palette();
    return { ...base(c, "fps"), series: [{ name: "Frame rate", type: "line", showSymbol: false, step: "end",
      lineStyle: { width: 2, color: c.smoke }, itemStyle: { color: c.smoke }, data: series(rows, (s) => s.fps) }] } as EChartsOption;
  }, [rows]);
  return <Chart title="Frame rate" option={option} testId="chart-fps" />;
}

export function PipelineBand({ tl }: { tl: Timeline }) {
  const option = useMemo(() => {
    const c = palette();
    const colors: Record<string, string> = { active: c.fire, scanning: c.good, idle: c.line };
    const segs = segments(tl);
    return {
      grid: { left: 48, right: 16, top: 8, bottom: 28 },
      tooltip: { trigger: "item", backgroundColor: c.surface, borderColor: c.line, textStyle: { color: c.text },
        formatter: (p: any) => `${p.data.state}: ${Math.round((p.data.value[1] - p.data.value[0]) / 1000)} s` },
      xAxis: { type: "time", axisLabel: { color: c.muted }, axisLine: { lineStyle: { color: c.line } } },
      yAxis: { type: "category", data: ["pipeline"], axisLabel: { show: false }, axisTick: { show: false }, axisLine: { show: false } },
      series: [{
        type: "custom", encode: { x: [0, 1], y: 2 },
        renderItem: (_p: any, api: any) => {
          const s = api.coord([api.value(0), 0]), e = api.coord([api.value(1), 0]), h = api.size([0, 1])[1] * 0.6;
          return { type: "rect", shape: { x: s[0], y: s[1] - h / 2, width: Math.max(1, e[0] - s[0]), height: h },
            style: { fill: colors[segs[_p.dataIndex]?.state] ?? c.line } };
        },
        data: segs.map((g) => ({ value: [g.start * 1000, g.end * 1000, 0], state: g.state })),
      }],
    } as EChartsOption;
  }, [tl]);
  return <Chart title="Pipeline state (idle · scanning · YOLO active)" option={option} height={110} testId="chart-pipeline" />;
}
