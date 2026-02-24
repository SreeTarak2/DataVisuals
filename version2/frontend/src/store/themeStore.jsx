import { create } from "zustand";
import { persist } from "zustand/middleware";

const DARK_QUERY = "(prefers-color-scheme: dark)";
let mediaQueryListenerAttached = false;

const getResolvedTheme = (theme) => {
  if (theme === "system" && typeof window !== "undefined") {
    return window.matchMedia(DARK_QUERY).matches ? "dark" : "light";
  }
  return theme === "light" ? "light" : "dark";
};

const applyThemeToDom = (theme) => {
  const resolvedTheme = getResolvedTheme(theme);
  if (typeof window !== "undefined") {
    const root = window.document.documentElement;
    root.classList.remove("light", "dark");
    root.classList.add(resolvedTheme);
  }
  return resolvedTheme;
};

const attachSystemThemeListener = (set, get) => {
  if (typeof window === "undefined" || mediaQueryListenerAttached) return;
  const mediaQuery = window.matchMedia(DARK_QUERY);

  const handler = () => {
    if (get().theme !== "system") return;
    const resolvedTheme = applyThemeToDom("system");
    set({ resolvedTheme });
  };

  mediaQuery.addEventListener("change", handler);
  mediaQueryListenerAttached = true;
};

const useThemeStore = create(
  persist(
    (set, get) => ({
      theme: "dark",
      resolvedTheme: "dark",

      setTheme: (theme) => {
        const normalizedTheme =
          theme === "light" || theme === "dark" || theme === "system"
            ? theme
            : "dark";
        const resolvedTheme = applyThemeToDom(normalizedTheme);
        if (normalizedTheme === "system") {
          attachSystemThemeListener(set, get);
        }
        set({ theme: normalizedTheme, resolvedTheme });
      },

      toggleTheme: () => {
        const nextTheme = get().resolvedTheme === "dark" ? "light" : "dark";
        get().setTheme(nextTheme);
      },

      // Initialize theme on app load
      initTheme: () => {
        const theme = get().theme;
        const resolvedTheme = applyThemeToDom(theme);
        if (theme === "system") {
          attachSystemThemeListener(set, get);
        }
        set({ resolvedTheme });
      },
    }),
    {
      name: "datasage-theme",
      onRehydrateStorage: () => (state) => {
        if (!state) return;
        const resolvedTheme = applyThemeToDom(state.theme || "dark");
        if (state.theme === "system") {
          attachSystemThemeListener(useThemeStore.setState, useThemeStore.getState);
        }
        useThemeStore.setState({ resolvedTheme });
      },
    }
  )
);

// Convenience hook that matches the old Context API
export const useTheme = () => {
  const theme = useThemeStore((state) => state.theme);
  const resolvedTheme = useThemeStore((state) => state.resolvedTheme);
  const toggleTheme = useThemeStore((state) => state.toggleTheme);
  const setTheme = useThemeStore((state) => state.setTheme);
  return { theme, resolvedTheme, toggleTheme, setTheme };
};

export default useThemeStore;
