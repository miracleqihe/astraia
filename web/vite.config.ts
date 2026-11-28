import react from '@vitejs/plugin-react';
import { defineConfig, type Plugin } from 'vite';

// Every browser supporting ES modules supports WOFF2; strip duplicate legacy .woff URLs from @fontsource CSS.
function woff2OnlyFontsource(): Plugin {
  return {
    name: 'astraia-woff2-only-fontsource',
    enforce: 'pre',
    transform(code, id) {
      if (!id.includes('fontsource') || !id.endsWith('.css') || !/format\(['"]woff['"]\)/.test(code)) return null;
      return {
        code: code.replace(/,\s*url\([^)]+\.woff\)\s*format\(['"]woff['"]\)/g, ''),
        map: null,
      };
    },
  };
}

export default defineConfig(({ command }) => ({
  // Development runs at the local root; the public site lives under /astraia/.
  base: command === 'serve' ? '/' : '/astraia/',
  plugins: [woff2OnlyFontsource(), react()],
  build: {
    rollupOptions: { input: ['index.html', 'ui-review/index.html', 'syzygy/index.html'] },
  },
  // The review index is regenerated atomically by Python. On Windows a file
  // watcher can keep the large data file open and prevent that replacement.
  // Review data is loaded on page refresh, so it does not need HMR watching.
  server: { watch: { ignored: ['**/public/review/data.js'] } },
}));
