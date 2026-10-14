import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir:'./tests/checklists',workers:1,timeout:30000,reporter:'list',outputDir:'test-results/checklists',
  use:{baseURL:'http://127.0.0.1:3024',launchOptions:process.env.AYS_CHROMIUM_EXECUTABLE?{executablePath:process.env.AYS_CHROMIUM_EXECUTABLE}:undefined,screenshot:'only-on-failure'},
  webServer:{command:'node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 3024 --strictPort',url:'http://127.0.0.1:3024',reuseExistingServer:false},
});
