import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e', testMatch: 'projects-acceptance.spec.ts',
  workers: 1, retries: 0, timeout: 120_000,
  reporter: [['./tests/people-safe-reporter.ts']],
  outputDir: '/artifacts/projects-browser',
  use: { baseURL: 'http://proxy', trace: 'off', screenshot: 'off', video: 'off',
         viewport: {width: 1440, height: 1000} },
});
