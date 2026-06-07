/**
 * PostCSS configuration for Tailwind CSS v4.
 *
 * Tailwind v4 uses @tailwindcss/postcss (a separate package from tailwindcss itself)
 * as the PostCSS plugin. This replaces the v3 pattern of "tailwindcss" as a PostCSS
 * plugin directly.
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.1 — Tailwind v4 functional setup.
 */
const config = {
  plugins: {
    "@tailwindcss/postcss": {},
  },
};

export default config;
