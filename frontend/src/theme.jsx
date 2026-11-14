// Light / dark theme. The first time, it follows the phone or laptop setting; the toggle button
// overrides it and the choice is remembered in this browser (localStorage).
// The colours themselves are CSS variables in styles.css, switched by <html data-theme="dark">.
import { createContext, useContext, useEffect, useState } from 'react';
import { Moon, Sun } from 'lucide-react';
import { applyChartTheme } from './components/charts.js';

const KEY = 'coldchain-theme';
const ThemeContext = createContext({ theme: 'light', toggle: () => {} });

function savedTheme() {
  try {
    const value = localStorage.getItem(KEY);
    if (value === 'light' || value === 'dark') return value;
  } catch {
    // storage blocked (private window): just follow the system
  }
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

// Called in main.jsx before the first render, so the page never flashes the wrong colours
export function applyTheme(theme = savedTheme()) {
  document.documentElement.dataset.theme = theme;
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'dark' ? '#0b1220' : '#ffffff');
  applyChartTheme(theme);
  return theme;
}

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme || savedTheme());

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  function toggle() {
    const next = theme === 'dark' ? 'light' : 'dark';
    try {
      localStorage.setItem(KEY, next);
    } catch {
      // not saved, still switches for this visit
    }
    applyTheme(next);   // first, so the charts already get the new colours when they redraw
    setTheme(next);
  }

  return <ThemeContext.Provider value={{ theme, toggle }}>{children}</ThemeContext.Provider>;
}

export const useTheme = () => useContext(ThemeContext);

export function ThemeToggle({ className = '' }) {
  const { theme, toggle } = useTheme();
  const dark = theme === 'dark';
  return (
    <button type="button" className={`icon-button theme-toggle ${className}`} onClick={toggle}
      aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'} title={dark ? 'Light mode' : 'Dark mode'}>
      <span className="theme-icon" key={theme}>{dark ? <Sun size={18} /> : <Moon size={18} />}</span>
    </button>
  );
}
