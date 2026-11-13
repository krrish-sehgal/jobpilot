"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "./ThemeProvider";

/** Flips between light and dark. Uses the effective theme so the first click always changes something. */
export function ThemeToggle() {
  const { setTheme } = useTheme();

  const toggle = () => {
    const effective =
      document.documentElement.getAttribute("data-theme") ??
      (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    setTheme(effective === "dark" ? "light" : "dark");
  };

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label="Toggle color theme"
      className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-muted hover:bg-sunken hover:text-ink"
    >
      <Sun className="dark-show h-4 w-4" aria-hidden />
      <Moon className="h-4 w-4 dark-hide" aria-hidden />
    </button>
  );
}
