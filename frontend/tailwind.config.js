/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        railDark: '#121212',
        railPanel: '#1e1e1e',
        railRed: '#ff4444',
        railGreen: '#00C851',
        railYellow: '#ffbb33'
      }
    },
  },
  plugins: [],
}
