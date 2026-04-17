/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './ops_portal/templates/**/*.html',
    './ops_portal/*/templates/**/*.html',
    './ops_portal/static/**/*.js',
  ],
  theme: {
    extend: {
      fontFamily: { sans: ['Segoe UI', 'system-ui', 'sans-serif'] },
      colors: {
        brand:   { DEFAULT: '#8251EE', hover: '#9366F5', light: '#A37EF5', subtle: 'rgba(130,81,238,0.15)' },
        surface: { 1: 'hsl(240,6%,10%)', 2: 'hsl(240,5%,12%)', 3: 'hsl(240,5%,14%)', 4: 'hsl(240,4%,18%)', 5: 'hsl(240,4%,22%)', 6: 'hsl(240,4%,26%)' },
        ink:     { primary: '#FFFFFF', secondary: '#A1A1AA', muted: '#71717A' },
        edge:    { subtle: 'hsla(0,0%,100%,0.06)', DEFAULT: 'hsla(0,0%,100%,0.10)', strong: 'hsla(0,0%,100%,0.18)' },
        ok:      '#10B981',
        warn:    '#F59E0B',
        danger:  '#EF4444',
        info:    '#3B82F6',
      },
      boxShadow: { glow: '0 0 24px rgba(130,81,238,0.25)', card: '0 4px 24px rgba(0,0,0,0.4)' },
      animation: { 'fade-in': 'fadeIn .2s ease-out', 'slide-up': 'slideUp .25s ease-out' },
      keyframes: {
        fadeIn:  { from: { opacity: 0 }, to: { opacity: 1 } },
        slideUp: { from: { opacity: 0, transform: 'translateY(8px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
      },
    },
  },
  plugins: [],
}
