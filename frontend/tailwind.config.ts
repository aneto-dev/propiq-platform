/**
 * Tailwind CSS configuration.
 *
 * Roadmap: IMPLEMENTATION_ROADMAP.md Commit 7.1 — this file is required by the
 * roadmap file list.
 *
 * Tailwind v4 uses CSS-first configuration — actual setup lives in
 * app/globals.css (@import "tailwindcss") and postcss.config.mjs.
 * This file is not auto-loaded by v4; it exists for roadmap compliance and
 * can be referenced via @config directive in CSS if JS-based customisation
 * is needed in a future commit.
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.1.
 */

const config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
} as const;

export default config;
