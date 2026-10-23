import { defineConfig } from "vite";
import { fileURLToPath } from "node:url";

export default defineConfig({
  server: {
    host: "127.0.0.1", port: 5173, strictPort: true,
    fs: { strict: true, allow: [fileURLToPath(new URL(".", import.meta.url)), fileURLToPath(new URL("../examples/synthetic", import.meta.url))] },
  },
  build: { sourcemap: false, target: "es2022" },
});
