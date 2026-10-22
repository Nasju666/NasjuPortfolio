// @ts-check
import { defineConfig } from 'astro/config';

// When you deploy, set `site` to your real URL (used for meta tags / sitemap).
// For GitHub Pages under a repo name, also set `base: '/<repo-name>'`.
export default defineConfig({
  site: 'https://nasju.me',
  // Hides Astro's developer toolbar (the small bar at the bottom during `npm run dev`).
  // It never appears on the live site either way. Set to true if you want it back.
  devToolbar: { enabled: false },
  build: {
    // Small CSS gets inlined into the HTML so the first paint needs one request.
    inlineStylesheets: 'auto',
  },
  vite: {
    build: {
      // three.js is only loaded when someone enters the room, so a big lazy chunk is expected.
      chunkSizeWarningLimit: 800,
    },
  },
});
