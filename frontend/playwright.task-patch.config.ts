import { defineConfig } from '@playwright/test';
export default defineConfig({testDir: './tests/task-patch', timeout: 30000, workers: 1, use: {baseURL: 'http://127.0.0.1:3017', trace: 'retain-on-failure'}, outputDir: process.env.AYS_TASK_PATCH_OUTPUT || 'test-results/task-patch'});
