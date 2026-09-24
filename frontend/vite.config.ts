import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // The backend's FRONTEND_URL / CORS_ORIGINS default to http://localhost:3000
  server: { port: 3000, strictPort: true },
  preview: { port: 3000 },
});
