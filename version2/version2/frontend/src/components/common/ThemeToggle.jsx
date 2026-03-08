import React from 'react';
import { Moon, Sun } from 'lucide-react';
import { useTheme } from '../../store/themeStore';

const ThemeToggle = () => {
  const { resolvedTheme, toggleTheme } = useTheme();

  return (
    <button
      onClick={toggleTheme}
      className="p-2 rounded-lg bg-white/10 dark:bg-black/20 backdrop-blur-md border border-white/20 hover:bg-white/20 dark:hover:bg-black/30 transition-all duration-300"
      aria-label="Toggle theme"
    >
      {resolvedTheme === 'dark' ? (
        <Sun className="h-5 w-5 text-yellow-300" />
      ) : (
        <Moon className="h-5 w-5 text-slate-700" />
      )}
    </button>
  );
};

export default ThemeToggle;
