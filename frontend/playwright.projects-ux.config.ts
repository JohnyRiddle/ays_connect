import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e', testMatch: ['projects-ux-preview.spec.ts','account-navigation.spec.ts'],
  workers: 1, retries: 0, timeout: 120_000,
  reporter: [['./tests/people-safe-reporter.ts']],
  outputDir: '/artifacts/projects-ux-browser',
  use: { baseURL: 'http://proxy', trace: 'off', screenshot: 'off', video: 'off' },
});
