import { defineConfig } from 'astro/config';

// GitHub Pages serves the site at https://<user>.github.io/<repo>/.
// If the repo gets a different name, change `base` to match it.
// With a custom domain, set `site` to that domain and remove `base`.
export default defineConfig({
  site: 'https://janadamiak.github.io',
  base: '/TeamTennants',
  trailingSlash: 'always',
});
