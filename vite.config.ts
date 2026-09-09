import { defineConfig } from 'vite';

/**
 * GitHub Pages serves a project site from `/<repo>/`, so a production build has
 * to know its sub-path. Development stays at `/` so `npm run dev` needs no
 * special URL.
 *
 * This is the only place the deployment path appears: the data source builds
 * every fetch from `import.meta.env.BASE_URL`, and index.html's asset URLs are
 * rewritten by Vite. Moving the site elsewhere is a change to this line.
 */
export default defineConfig(({ command, isPreview }) => ({
  // `vite preview` runs with command === 'serve', so it has to be named
  // explicitly or it would serve a build made for the sub-path at the root and
  // silently answer every data request with the fallback page. Preview is the
  // rehearsal for the deployed site, so it must use the same base as the build.
  base: command === 'build' || isPreview ? '/Weather-Analysis/' : '/',
}));
