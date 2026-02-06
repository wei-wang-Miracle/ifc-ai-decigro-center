/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{vue,js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#E8F0FE',  // AI Bubble / Highlight
          100: '#D2E3FC',
          500: '#4285F4', // Google Blue (Primary)
          600: '#1A73E8', // Hover
          700: '#1967D2', // Sidebar
          900: '#174EA6', // Sidebar Active
        },
        growth: '#34A853', // Financial Positive
        risk: '#EA4335',   // Financial Negative
      },
      fontFamily: {
        sans: ['Inter', 'PingFang SC', 'sans-serif'],
        mono: ['JetBrains Mono', 'Roboto Mono', 'monospace'], // 核心数据字体
      },
      boxShadow: {
        'bento': '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
        'bento-hover': '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
      },
      animation: {
        'cursor-blink': 'blink 1s step-end infinite',
      },
      keyframes: {
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        }
      }
    },
  },
  plugins: [],
};
