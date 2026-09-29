import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

// Light/dark theme. The choice ("system" follows the OS) is kept in localStorage; the inline
// script in index.html applies it before first paint so a dark page never flashes white.

export type ThemeChoice = "light" | "dark" | "system";
type Resolved = "light" | "dark";

const KEY = "dm.theme";
const QUERY = "(prefers-color-scheme: dark)";
const BAR = { light: "#6b2de8", dark: "#0d0b14" };

type Theme = { choice: ThemeChoice; resolved: Resolved; setChoice: (c: ThemeChoice) => void; toggle: () => void };

const ThemeContext = createContext<Theme | null>(null);

function readChoice(): ThemeChoice {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "light" || v === "dark" || v === "system") return v;
  } catch {
    // storage unavailable
  }
  return "system";
}

const systemDark = () => typeof matchMedia !== "undefined" && matchMedia(QUERY).matches;

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [choice, setChoiceState] = useState<ThemeChoice>(readChoice);
  const [osDark, setOsDark] = useState(systemDark);
  const resolved: Resolved = choice === "system" ? (osDark ? "dark" : "light") : choice;

  // follow the OS while the choice is "system"
  useEffect(() => {
    const mq = matchMedia(QUERY);
    const onChange = () => setOsDark(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", resolved === "dark");
    root.style.colorScheme = resolved;
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", BAR[resolved]);
  }, [resolved]);

  const setChoice = useCallback((c: ThemeChoice) => {
    // cross-fade colours for a moment (see .theme-switching in index.css)
    const root = document.documentElement;
    root.classList.add("theme-switching");
    window.setTimeout(() => root.classList.remove("theme-switching"), 400);
    setChoiceState(c);
    try {
      localStorage.setItem(KEY, c);
    } catch {
      // storage unavailable
    }
  }, []);

  const value = useMemo<Theme>(
    () => ({ choice, resolved, setChoice, toggle: () => setChoice(resolved === "dark" ? "light" : "dark") }),
    [choice, resolved, setChoice],
  );
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): Theme {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme outside ThemeProvider");
  return ctx;
}
