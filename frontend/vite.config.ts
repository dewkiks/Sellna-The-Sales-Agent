import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// The `@/*` import alias resolves to the project root, matching the alias
// previously provided by the Next.js tsconfig `paths` setting.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
  server: {
    port: 8080,
  },
});
