import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// host:true → listen on 0.0.0.0 so the dev server is reachable from outside the
// container. usePolling → reliable file-watching across the docker bind mount.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    watch: { usePolling: true },
  },
})
