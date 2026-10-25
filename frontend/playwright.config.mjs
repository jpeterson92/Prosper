import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 45000,
  workers: 4,
  fullyParallel: true,
  reporter: [["list"]],
  outputDir: "../.local/browser-results",
  use: { browserName: "chromium", trace: "off", video: "off", screenshot: "off" },
});
