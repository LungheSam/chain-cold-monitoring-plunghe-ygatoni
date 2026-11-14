import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    // frontend/dist, served on Railway by server.mjs (`npm start`)
    outDir: 'dist',
    emptyOutDir: true,
    // The Firebase SDK chunk is about 560 kB (loaded once, cached). Not worth splitting further.
    chunkSizeWarningLimit: 700,
  },
  test: {
    environment: 'node',
  },
});
