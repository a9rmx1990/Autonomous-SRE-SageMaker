import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx}',
    './components/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        sre: {
          bg: '#0a0e14',
          surface: '#111820',
          raised: '#1a2230',
          border: '#1e2a3a',
          'border-light': '#2a3a4e',
          text: '#c8d6e5',
          'text-dim': '#6b7d8e',
          'text-bright': '#e8f0f8',
          accent: '#00d4aa',
          'accent-dim': '#00a885',
          warning: '#f0a830',
          error: '#e84057',
          info: '#3a8fd4',
          success: '#00d4aa',
          critical: '#e84057',
          high: '#f0a830',
          medium: '#3a8fd4',
          low: '#6b7d8e',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow': 'glow 2s ease-in-out infinite alternate',
      },
      keyframes: {
        glow: {
          '0%': { opacity: '0.4' },
          '100%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
};

export default config;
