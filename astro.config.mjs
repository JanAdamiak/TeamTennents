import { defineConfig } from 'astro/config';

// Served from the custom domain set in the repo's Settings → Pages.
export default defineConfig({
  site: 'https://teamtennents.uk',
  trailingSlash: 'always',
});
