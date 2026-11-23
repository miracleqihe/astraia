import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  base: './',
  plugins: [react()],
  // The review index is regenerated atomically by Python. On Windows a file
  // watcher can keep the large data file open and prevent that replacement.
  // Review data is loaded on page refresh, so it does not need HMR watching.
  server: { watch: { ignored: ['**/public/review/data.js'] } },
});
