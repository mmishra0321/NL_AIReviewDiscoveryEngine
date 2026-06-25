/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Spotify-inspired palette
        bg: {
          DEFAULT: "#0a0a0b",      // page
          elevated: "#161618",     // cards
          subtle:   "#1d1d20",     // inner panels
          hover:    "#222227",
        },
        border: {
          DEFAULT: "#262629",
          strong:  "#363639",
        },
        fg: {
          DEFAULT: "#f5f5f5",
          muted:   "#9ca3af",
          subtle:  "#6b7280",
        },
        brand: {
          DEFAULT: "#1DB954",      // Spotify green
          fg:      "#0a0a0b",
          hover:   "#1ed760",
          dim:     "#0d4a26",
        },
        danger: "#ef4444",
        warn:   "#f59e0b",
        info:   "#3b82f6",
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      boxShadow: {
        card: "0 1px 0 rgba(255,255,255,0.04) inset, 0 8px 24px rgba(0,0,0,0.35)",
        glow: "0 0 0 1px rgba(29,185,84,0.4), 0 8px 28px rgba(29,185,84,0.18)",
      },
      animation: {
        shimmer: "shimmer 1.6s linear infinite",
        "fade-in": "fade-in 220ms ease-out",
        "slide-up": "slide-up 240ms ease-out",
      },
      keyframes: {
        shimmer: {
          "0%":   { backgroundPosition: "-1000px 0" },
          "100%": { backgroundPosition: "1000px 0" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to:   { opacity: "1" },
        },
        "slide-up": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to:   { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};
