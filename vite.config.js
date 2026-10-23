import { defineConfig } from 'vite';
// blender/ and qa/ hold renders and test captures; watching them would reload the page mid-render.
// SDC_BASE: where the site is served from (GitHub Pages serves it under /squaredc-home/; Netlify at the root).
export default defineConfig({
  base: process.env.SDC_BASE || '/',
  server: { port: 4250, strictPort: true, host: true, watch: { ignored: ['**/blender/**', '**/qa/**', '**/dist/**'] } },
});
