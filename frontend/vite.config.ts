import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    // Vite's DNS-rebinding protection rejects requests whose Host header
    // isn't localhost/an IP/a name Vite already knows about. This project
    // is accessed over Tailscale by machine name (see CLAUDE.md: single
    // user via Tailnet), so that name needs to be allow-listed explicitly.
    allowedHosts: ["homepi"],
    // Dev-time only: lets the browser call the backend as if it were same
    // origin, so no CORS configuration is needed until Phase6-1 (which
    // wires CORS for the production build instead). "backend" resolves via
    // Docker Compose's default network -- this assumes the app is always
    // run through `docker compose up`, per this project's policy of never
    // installing directly on the host.
    proxy: {
      "/pdfs": "http://backend:8000",
      "/scan": "http://backend:8000",
      "/generation-jobs": "http://backend:8000",
      "/settings": "http://backend:8000",
    },
  },
})
