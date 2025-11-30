import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0', // Listen on all interfaces for external access
    port: 5173,
    cors: true, // Enable CORS for all origins
    // Проксирование API запросов на бэкенд
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
        // Важно: не используем rewrite, так как бэкенд ожидает /api в пути
        // rewrite: (path) => path.replace(/^\/api/, '') - НЕ используем!
        configure: (proxy, options) => {
          // Устанавливаем правильный host header
          proxy.on('proxyReq', (proxyReq, req, res) => {
            // Убеждаемся, что Host header установлен правильно
            proxyReq.setHeader('Host', 'localhost:8000');
            // Логируем для отладки
            const targetUrl = `${options.target}${req.url}`;
            console.log('[Vite Proxy] Request:', req.method, req.url);
            console.log('[Vite Proxy] Target:', options.target);
            console.log('[Vite Proxy] Full target URL:', targetUrl);
            // Увеличиваем таймауты для длительных запросов
            proxyReq.setTimeout(1200000); // 20 минут
          });
          
          proxy.on('error', (err, req, res) => {
            console.error('[Vite Proxy] Error:', err.message);
            console.error('[Vite Proxy] Request URL:', req.url);
            console.error('[Vite Proxy] Error code:', err.code);
            if (res && !res.headersSent) {
              res.writeHead(500, {
                'Content-Type': 'text/plain',
              });
              res.end('Proxy error: ' + err.message);
            }
          });
          
          proxy.on('proxyRes', (proxyRes, req, res) => {
            console.log('[Vite Proxy] Response:', proxyRes.statusCode, req.url);
            if (proxyRes.statusCode === 307 || proxyRes.statusCode === 308) {
              console.warn('[Vite Proxy] Redirect detected:', proxyRes.statusCode);
              console.warn('[Vite Proxy] Location header:', proxyRes.headers.location);
            }
            if (proxyRes.statusCode >= 400) {
              console.error('[Vite Proxy] Error response:', proxyRes.statusCode, req.url);
            }
          });
        },
      },
    },
  },
})
