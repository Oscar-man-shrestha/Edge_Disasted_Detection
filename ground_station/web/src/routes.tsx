import { lazy, Suspense } from "react";
import { Redirect, Route, Switch } from "wouter";
import { ErrorBoundary } from "./features/shell/ErrorBoundary";
import LiveView from "./features/live/LiveView";
import MissionsView from "./features/missions/MissionsView";

const ReplayView = lazy(() => import("./features/replay/ReplayView"));
const AnalyticsView = lazy(() => import("./features/analytics/AnalyticsView"));

const Loading = () => <div className="grid h-full place-items-center text-sm text-muted">Loading…</div>;

export function AppRoutes() {
  return (
    <Suspense fallback={<Loading />}>
      <Switch>
        <Route path="/live"><ErrorBoundary name="Live"><LiveView /></ErrorBoundary></Route>
        <Route path="/replay/:id?">{(p) => <ErrorBoundary name="Replay"><ReplayView missionId={num(p.id)} /></ErrorBoundary>}</Route>
        <Route path="/analytics/:id?">{(p) => <ErrorBoundary name="Analytics"><AnalyticsView missionId={num(p.id)} /></ErrorBoundary>}</Route>
        <Route path="/missions"><ErrorBoundary name="Missions"><MissionsView /></ErrorBoundary></Route>
        <Route><Redirect to="/live" /></Route>
      </Switch>
    </Suspense>
  );
}

function num(v: string | undefined): number | undefined {
  const n = v ? Number(v) : NaN;
  return Number.isFinite(n) ? n : undefined;
}
