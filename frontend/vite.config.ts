import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [tailwindcss(), sveltekit()],
  server: {
    port: 5173,
    // In dev we run the SvelteKit dev server alongside the FastAPI backend
    // and forward every backend-owned path. The list mirrors the prefixes
    // mounted by `app.main.create_app()`.
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true
      },
      '/run': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true
      },
      '/p': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  }
});
