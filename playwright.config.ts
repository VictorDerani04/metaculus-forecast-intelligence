import {defineConfig, devices} from '@playwright/test';

export default defineConfig({
  testDir: 'tests/e2e',
  fullyParallel: false,
  reporter: [['line']],
  use: {
    baseURL: 'http://127.0.0.1:3000',
    trace: 'on-first-retry',
  },
  webServer: [
    {
      command: 'py -m uvicorn app.main:app --host 127.0.0.1 --port 8000',
      cwd: 'apps/api',
      url: 'http://127.0.0.1:8000/health',
      reuseExistingServer: !process.env.CI,
      env: {
        DATABASE_URL: 'sqlite:///./e2e-private-core.db',
        SESSION_SECRET: 'e2e-private-core-secret',
        PRIVATE_USER_EMAIL: process.env.E2E_EMAIL ?? 'owner@example.com',
        PRIVATE_USER_PASSWORD: process.env.E2E_PASSWORD ?? 'correct horse battery staple',
        WEB_ORIGIN: 'http://127.0.0.1:3000',
      },
    },
    {
      command: 'npm.cmd run dev -- --hostname 127.0.0.1 --port 3000',
      cwd: 'apps/web',
      url: 'http://127.0.0.1:3000/login',
      reuseExistingServer: !process.env.CI,
      env: {
        NEXT_PUBLIC_API_BASE_URL: 'http://127.0.0.1:8000',
      },
    },
  ],
  projects: [{name: 'chromium', use: {...devices['Desktop Chrome']}}],
});
