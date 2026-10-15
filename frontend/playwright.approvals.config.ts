import {defineConfig} from '@playwright/test';
export default defineConfig({
  testDir:'./tests/approvals',workers:1,timeout:90000,reporter:'list',outputDir:'test-results/approvals',
  use:{baseURL:process.env.AYS_APPROVAL_UI_URL||'http://127.0.0.1:3035',launchOptions:process.env.AYS_CHROMIUM_EXECUTABLE?{executablePath:process.env.AYS_CHROMIUM_EXECUTABLE}:undefined,screenshot:'only-on-failure'},
});
