import { useEffect } from "react";
import { usePrefs } from "../store/ui";

export function useTheme(): void {
  const theme = usePrefs((s) => s.prefs.theme);
  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);
  }, [theme]);
}

export function isDark(): boolean {
  const t = document.documentElement.getAttribute("data-theme");
  if (t) return t === "dark";
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? true;
}
