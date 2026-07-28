import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// The dev server proxies API calls to FastAPI so the browser only ever talks to
// one origin. Both servers bind to 127.0.0.1 only (SOW 6.4 — privacy by architecture).
//
// The long timeouts matter: a resume/question generation is a single POST that
// stays silent for ~2 minutes on CPU before replying. The proxy's default idle
// timeout would sever that connection mid-generation, so the browser would hang
// even though the backend is working fine. 15 minutes covers the slowest case.
const backend = {
  target: 'http://127.0.0.1:8000',
  changeOrigin: true,
  timeout: 900000, // browser -> vite socket idle timeout (ms)
  proxyTimeout: 900000, // vite -> backend response timeout (ms)
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/health': backend,
      '/api': backend,
    },
  },
})
