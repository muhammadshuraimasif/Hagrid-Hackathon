import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.ico', 'audio/*.mp3'],
      manifest: {
        name: 'Amaanat - Relief Grant Portal (PROTOTYPE)',
        short_name: 'Amaanat',
        description: 'DPI Relief Grant Portal Prototype for Pakistan',
        theme_color: '#006633',
        background_color: '#f8fafc',
        display: 'standalone',
        icons: [
          {
            src: 'favicon.ico',
            sizes: '64x64 32x32 24x24 16x16',
            type: 'image/x-icon',
          },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,mp3}'],
        // Never let the SPA service worker hijack backend pages (Swagger docs, API, health checks)
        navigateFallbackDenylist: [/^\/api\//, /^\/docs/, /^\/redoc/, /^\/openapi\.json/, /^\/health/, /^\/ready/],
      },
    }),
  ],
  server: {
    port: 3000,
    host: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'node',
  },
});
