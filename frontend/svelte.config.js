import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({
      pages: 'build',
      assets: 'build',
      // Use index.html as the SPA fallback so client-side routes
      // ([id], etc.) work when the FastAPI static mount serves them.
      fallback: 'index.html',
      precompress: false,
      strict: false
    }),
    // The whole app is rendered client-side (SPA). The backend handles
    // its own auth / sessions; we don't want SvelteKit prerendering the
    // marketing-style content because per-request behaviour (logged-in
    // gallery, "my notebooks") is what we actually need.
    prerender: { entries: [] }
  }
};

export default config;
