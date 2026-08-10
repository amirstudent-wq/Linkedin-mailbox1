import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        linkedin: {
          50: "#eef3fb",
          100: "#c9dbf3",
          200: "#93b8e7",
          300: "#5c94da",
          400: "#2d71cf",
          500: "#0a66c2",
          600: "#084fa0",
          700: "#063a7c",
          800: "#04265a",
          900: "#021438",
        },
      },
    },
  },
  plugins: [],
};
export default config;
