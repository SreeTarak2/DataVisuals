import { fileURLToPath } from 'url';
import path from "path"
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import fs from 'fs'

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

function saveLogoPlugin() {
  return {
    name: 'save-logo-plugin',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if (req.url === '/local-api/save-logo' && req.method === 'POST') {
          let body = '';
          req.on('data', chunk => {
            body += chunk.toString();
          });
          req.on('end', () => {
            try {
              const { base64Data } = JSON.parse(body);
              const data = base64Data.replace(/^data:image\/png;base64,/, "");
              const filePath = path.resolve(__dirname, 'public/logo.png');
              fs.writeFileSync(filePath, data, 'base64');
              console.log('--- LOGO SAVED SUCCESSFULLY ---');
              res.writeHead(200, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ success: true }));
            } catch (err) {
              console.error('--- ERROR SAVING LOGO ---', err);
              res.writeHead(500, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ error: err.message }));
            }
          });
        } else {
          next();
        }
      });
    }
  };
}

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss(), saveLogoPlugin()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 3000,
    host: true,
    allowedHosts: [
      'fighting-habitat-appointment-sega.trycloudflare.com'
    ],
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
  define: {
    'process.env.API_URL': JSON.stringify(process.env.API_URL || 'http://localhost:8000'),
  },
})