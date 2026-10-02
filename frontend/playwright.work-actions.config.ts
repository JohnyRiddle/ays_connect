import { defineConfig } from '@playwright/test';
export default defineConfig({testDir:'./tests/e2e',testMatch:['work-actions-ux.spec.ts'],workers:1,retries:0,timeout:120_000,reporter:[['./tests/people-safe-reporter.ts']],outputDir:'/artifacts/work-actions-browser',use:{baseURL:'http://proxy',trace:'off',screenshot:'off',video:'off'}});
