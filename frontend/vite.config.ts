import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig(({ mode }) => {
  const target = new URL(loadEnv(mode, '..', 'KILLCHAIN_').KILLCHAIN_DEV_API || 'http://127.0.0.1:8000');
  if (target.protocol !== 'http:' || !['127.0.0.1', 'localhost'].includes(target.hostname) || target.username || target.password || target.pathname !== '/' || target.search || target.hash) {
    throw new Error('KILLCHAIN_DEV_API must be a loopback HTTP origin');
  }
  return {
  plugins: [react(), tailwindcss()],
  server: { proxy: { '/api': target.origin } },
  };
});
