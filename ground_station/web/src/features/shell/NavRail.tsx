import { ChartColumn, History, ListChecks, Radar } from "lucide-react";
import { Link, useLocation } from "wouter";
import { cn } from "../../ui/cn";

export const NAV = [
  { to: "/live", label: "Live", icon: Radar },
  { to: "/replay", label: "Replay", icon: History },
  { to: "/analytics", label: "Analytics", icon: ChartColumn },
  { to: "/missions", label: "Missions", icon: ListChecks },
] as const;

export function NavRail() {
  const [loc] = useLocation();
  const active = (to: string) => loc === to || loc.startsWith(to + "/");
  return (
    <>
      <nav aria-label="Views" className="hidden w-[68px] shrink-0 flex-col items-center gap-1 border-r border-line bg-surface py-3 md:flex">
        {NAV.map(({ to, label, icon: Icon }) => (
          <Link key={to} href={to} aria-current={active(to) ? "page" : undefined}
            className={cn("flex w-14 flex-col items-center gap-1 rounded-xl py-2 text-[10px] font-semibold",
              active(to) ? "bg-accent/15 text-accent" : "text-muted hover:bg-surface-2 hover:text-text")}>
            <Icon size={20} aria-hidden />{label}
          </Link>
        ))}
      </nav>
      <nav aria-label="Views" className="fixed inset-x-0 bottom-0 z-[1500] grid grid-cols-4 border-t border-line bg-surface md:hidden">
        {NAV.map(({ to, label, icon: Icon }) => (
          <Link key={to} href={to} aria-current={active(to) ? "page" : undefined}
            className={cn("flex flex-col items-center gap-0.5 py-2 text-[11px] font-semibold",
              active(to) ? "text-accent" : "text-muted")}>
            <Icon size={20} aria-hidden />{label}
          </Link>
        ))}
      </nav>
    </>
  );
}
