import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The page talks to the FastAPI backend at http://localhost:8000 directly (see src/api.ts);
// the backend allows this origin (http://localhost:5173) through CORS.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    open: true, // `npm run dev` opens the desk in your browser
  },
})
