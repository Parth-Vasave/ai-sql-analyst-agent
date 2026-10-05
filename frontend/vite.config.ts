import { fileURLToPath } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, type Connect, type Plugin } from 'vite'

// The dev and preview servers fall back to the homepage for unknown paths, so /chat (no slash)
// would show the homepage; static hosts resolve it to chat/index.html themselves.
const chatRedirect: Connect.NextHandleFunction = (req, res, next) => {
  if (req.url === '/chat' || req.url?.startsWith('/chat?')) {
    res.statusCode = 301
    res.setHeader('Location', req.url.replace('/chat', '/chat/'))
    res.end()
    return
  }
  next()
}

const chatTrailingSlash: Plugin = {
  name: 'chat-trailing-slash',
  configureServer: (server) => void server.middlewares.use(chatRedirect),
  configurePreviewServer: (server) => void server.middlewares.use(chatRedirect),
}

// Two pages: the project homepage at / and the chat app at /chat/. Plain static files, so any
// host serves both without rewrite rules.
export default defineConfig({
  plugins: [react(), tailwindcss(), chatTrailingSlash],
  build: {
    rolldownOptions: {
      input: {
        home: fileURLToPath(new URL('./index.html', import.meta.url)),
        chat: fileURLToPath(new URL('./chat/index.html', import.meta.url)),
      },
    },
  },
  server: {
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
