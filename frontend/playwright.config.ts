import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  use: {
    baseURL: process.env.AYS_E2E_BASE_URL || "https://localhost",
    ignoreHTTPSErrors: true,
    trace: "retain-on-failure",
    launchOptions: {
      args: ["--host-resolver-rules=MAP localhost host.docker.internal"],
    },
  },
});
