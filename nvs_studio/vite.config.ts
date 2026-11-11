import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
// Production build is served by the FastAPI Local Studio at /nvs/ (same origin as /api).
export default defineConfig(({ command }) => ({
  base: command === 'build' ? '/nvs/' : '/',
  plugins: [react(), tailwindcss()],
  server: { proxy: { '/api': { target: 'http://127.0.0.1:8776', changeOrigin: false } } },
  test: { environment: 'node' },
}));
