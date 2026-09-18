import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "../../packages/ui/src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        nexus: {
          950: "#06090e",
          900: "#0b101b",
          850: "#101726",
          800: "#162035",
          700: "#1f2d4a",
          cyan: "#00f2fe",
          blue: "#4facfe",
        },
      },
      fontFamily: {
        mono: ["JetBrains Mono", "SF Mono", "monospace"],
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
