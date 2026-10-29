/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        win: {
          bg: '#141417',
          surface: '#1C1C21',
          elevated: '#24242B',
          hover: '#2A2A33',
          border: 'rgba(255, 255, 255, 0.07)',
        },
        cat: {
          social: '#3B82F6',
          creative: '#06B6D4',
          entertainment: '#F59E0B',
          productivity: '#10B981',
          other: '#71717A',
        },
      },
      fontFamily: {
        sans: [
          '"Segoe UI Variable Display"',
          '"Segoe UI"',
          '"Microsoft YaHei UI"',
          '"Microsoft YaHei"',
          'system-ui',
          '-apple-system',
          'sans-serif',
        ],
      },
      boxShadow: {
        card: '0 8px 24px -4px rgba(0, 0, 0, 0.45), 0 2px 6px -1px rgba(0, 0, 0, 0.3)',
        floating: '0 12px 32px -4px rgba(0, 0, 0, 0.65), 0 4px 12px -2px rgba(0, 0, 0, 0.45)',
      },
    },
  },
  plugins: [],
}
