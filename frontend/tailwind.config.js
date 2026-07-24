/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        background: '#0F172A',
        foreground: '#F8FAFC',
        primary: '#1E293B',
        secondary: '#334155',
        accent: '#22C55E',
        destructive: '#EF4444',
        muted: '#272F42',
        mutedForeground: '#94A3B8',
        border: '#475569',
        // Phase E semantic aliases (intent names over raw hex; values match existing usage).
        surface: '#1E293B',
        warning: '#C98500',
      },
    },
  },
  plugins: [],
}
