import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Vite es el servidor de desarrollo: sirve las pantallas y, ademas, reenvia
// todo lo que empiece por /api hacia el backend (proxy). Asi el navegador
// cree que pantallas y API son el MISMO sitio, y la cookie segura de sesion
// funciona sin abrir permisos extra (CORS).
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    watch: { usePolling: true }, // para detectar cambios hechos desde Windows
    proxy: {
      '/api': {
        target: process.env.API_URL || 'http://backend:8000',
        changeOrigin: true,
        xfwd: true, // envia la IP real del navegador al backend
        rewrite: (ruta) => ruta.replace(/^\/api/, ''), // /api/auth/login -> /auth/login
        cookiePathRewrite: { '/auth': '/api/auth' }, // la cookie de sesion sigue limitada a autenticacion
      },
    },
  },
})
