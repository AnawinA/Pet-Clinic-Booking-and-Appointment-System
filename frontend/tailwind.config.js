/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eefbf5",
          100: "#d6f5e6",
          200: "#b5efd7",
          300: "#7eddb8",
          400: "#3cc78f",
          500: "#12a06a",
          600: "#0c8357",
          700: "#0a6846",
          800: "#08543a",
          900: "#06402d",
        },
      },
      fontFamily: {
        sans: ["Inter", "Noto Sans Thai", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
