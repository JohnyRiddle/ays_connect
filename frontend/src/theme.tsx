import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

export type Theme = "light" | "dark";
const storageKey = "ays-connect-theme";
const preference = window.matchMedia("(prefers-color-scheme: dark)");

function savedTheme(): Theme | null {
  try {
    const value = localStorage.getItem(storageKey);
    return value === "light" || value === "dark" ? value : null;
  } catch {
    return null;
  }
}

export function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
  document.querySelector('meta[name="theme-color"]')?.setAttribute(
    "content", theme === "dark" ? "#181817" : "#f5f4f2",
  );
}

export function ThemeSwitch() {
  const [theme, setTheme] = useState<Theme>(() =>
    savedTheme() ?? (preference.matches ? "dark" : "light"),
  );
  useEffect(() => {
    applyTheme(theme);
  }, [theme]);
  useEffect(() => {
    const systemChanged = () => {
      if (!savedTheme()) setTheme(preference.matches ? "dark" : "light");
    };
    const storageChanged = (event: StorageEvent) => {
      if (event.key === storageKey || event.key === null)
        setTheme(savedTheme() ?? (preference.matches ? "dark" : "light"));
    };
    preference.addEventListener("change", systemChanged);
    window.addEventListener("storage", storageChanged);
    return () => {
      preference.removeEventListener("change", systemChanged);
      window.removeEventListener("storage", storageChanged);
    };
  }, []);
  const toggle = () => {
    const next = theme === "light" ? "dark" : "light";
    try { localStorage.setItem(storageKey, next); } catch { /* Session-only preference. */ }
    setTheme(next);
  };
  return (
    <button type="button" className="theme-switch" onClick={toggle}
      aria-label={theme === "light" ? "Включить тёмную тему" : "Включить светлую тему"}
      title={theme === "light" ? "Тёмная тема" : "Светлая тема"}>
      {theme === "light" ? <Moon size={18} /> : <Sun size={18} />}
      <span>{theme === "light" ? "Тёмная" : "Светлая"}</span>
    </button>
  );
}
