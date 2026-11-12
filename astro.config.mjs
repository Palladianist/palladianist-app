import { defineConfig } from 'astro/config';
export default defineConfig({
  site: 'https://read.palladianist.org',
  trailingSlash: 'ignore',
  build: { format: 'directory' }
});
