import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const testPort = loadEnv(mode, '.', 'VISION_STUDIO_TEST_').VISION_STUDIO_TEST_BACKEND_PORT;
  return {
  plugins: [react()],
  envDir: '..',
  clearScreen: false,
  server: { host: '127.0.0.1', port: 1420, strictPort: true,
    proxy: testPort ? { '/qa-api': { target: `http://127.0.0.1:${testPort}`, rewrite: path => path.replace(/^\/qa-api/, '') } } : undefined,
  },
  };
});
