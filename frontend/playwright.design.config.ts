import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/design",
  workers: 1,
  retries: 0,
  timeout: 30000,
  reporter: "list",
  outputDir: "test-results/design",
  use: { baseURL: "http://127.0.0.1:3002", launchOptions: process.env.AYS_CHROMIUM_EXECUTABLE ? { executablePath: process.env.AYS_CHROMIUM_EXECUTABLE } : undefined, trace: "off", screenshot: "only-on-failure" },
  webServer: {
    command: "node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 3002 --strictPort",
    url: "http://127.0.0.1:3002",
    reuseExistingServer: false,
  },
});
