import {defineConfig} from '@playwright/test';
export default defineConfig({
 testDir:'./tests/chat-live',workers:1,timeout:45000,reporter:'list',
 use:{baseURL:'http://127.0.0.1:3037',launchOptions:process.env.AYS_CHROMIUM_EXECUTABLE?{executablePath:process.env.AYS_CHROMIUM_EXECUTABLE}:undefined,screenshot:'only-on-failure'},
 webServer:{command:'npm run dev -- --host 127.0.0.1 --port 3037',url:'http://127.0.0.1:3037/tests/chat-live/index.html',reuseExistingServer:false},
});
