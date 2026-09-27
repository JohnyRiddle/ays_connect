import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  testMatch: 'integrated-cards-iiko.spec.ts',
  workers: 1,
  retries: 0,
  timeout: 60_000,
  reporter: [['./tests/people-safe-reporter.ts']],
  outputDir: '/artifacts/integrated-browser',
  use: {
    baseURL: 'http://proxy',
    trace: 'off',
    screenshot: 'off',
    video: 'off',
    viewport: { width: 1440, height: 1000 },
  },
});
