import { create } from 'zustand';
import { persist } from 'zustand/middleware';

const useThemeStore = create(
    persist(
        (set, get) => ({
            theme: 'dark',

            toggleTheme: () => {
                const newTheme = get().theme === 'dark' ? 'light' : 'dark';
                // Update DOM classes
                const root = window.document.documentElement;
                root.classList.remove('light', 'dark');
                root.classList.add(newTheme);
                set({ theme: newTheme });
            },

            // Initialize theme on app load
            initTheme: () => {
                const theme = get().theme;
                const root = window.document.documentElement;
                root.classList.remove('light', 'dark');
                root.classList.add(theme);
            },
        }),
        {
            name: 'datasage-theme',
            onRehydrate: () => (state) => {
                // Apply theme to DOM when store rehydrates from localStorage
                if (state) {
                    const root = window.document.documentElement;
                    root.classList.remove('light', 'dark');
                    root.classList.add(state.theme);
                }
            },
        }
    )
);

// Convenience hook that matches the old Context API
export const useTheme = () => {
    const theme = useThemeStore((state) => state.theme);
    const toggleTheme = useThemeStore((state) => state.toggleTheme);
    return { theme, toggleTheme };
};

export default useThemeStore;
