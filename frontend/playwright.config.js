import { defineConfig } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { resolvePythonExecutable } from './e2e/cleanupLifecycle.js'

const frontendDirectory = path.dirname(fileURLToPath(import.meta.url))
const projectRoot = path.resolve(frontendDirectory, '..')
const backendDirectory = path.resolve(projectRoot, 'backend')
const frontendHost = '127.0.0.1'
const frontendPort = 5174
const frontendUrl = `http://${frontendHost}:${frontendPort}`
const frontendOrigins = `${frontendUrl},http://localhost:${frontendPort}`
const testDatabase = 'fittrack_test_20261116_a91f'
const testDatabaseUser = 'ft_test_20261116_a91f'
const testDatabaseHost = '127.0.0.1'
const python = resolvePythonExecutable(projectRoot, process.env.FITTRACK_E2E_PYTHON)
const runId = new Date().toISOString().replace(/[:.]/g, '-')
const outputDirectory = path.resolve(frontendDirectory, 'test-results', `run-${runId}`)
const reportDirectory = path.resolve(frontendDirectory, 'playwright-report', `run-${runId}`)
const e2eServerEnv = {
  ...process.env,
  FITTRACK_TEST_DB_NAME: process.env.FITTRACK_TEST_DB_NAME || '',
  FITTRACK_TEST_DB_HOST: process.env.FITTRACK_TEST_DB_HOST || '',
  FITTRACK_TEST_DB_USER: process.env.FITTRACK_TEST_DB_USER || '',
  FITTRACK_TEST_DB_PASSWORD: process.env.FITTRACK_TEST_DB_PASSWORD || '',
  FITTRACK_TEST_DB_CONFIRM: process.env.FITTRACK_TEST_DB_CONFIRM || '',
  FITTRACK_RUN_DB_TESTS: process.env.FITTRACK_RUN_DB_TESTS || '',
  DB_NAME: testDatabase,
  DB_HOST: testDatabaseHost,
  DB_USER: testDatabaseUser,
  DB_PASSWORD: process.env.FITTRACK_TEST_DB_PASSWORD || '',
  FITTRACK_ENV: 'development',
  PORT: '5000',
  FRONTEND_URL: frontendUrl,
  FRONTEND_ORIGINS: frontendOrigins,
  COOKIE_SECURE: 'false',
  FLASK_DEBUG: 'false',
}

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  retries: 0,
  reporter: [['list'], ['html', { outputFolder: reportDirectory, open: 'never' }]],
  webServer: [
    {
      command: `"${python}" tests/e2e_server.py`,
      cwd: backendDirectory,
      url: 'http://127.0.0.1:5000/api/health',
      timeout: 60_000,
      reuseExistingServer: false,
      env: e2eServerEnv,
    },
    {
      command: `npm.cmd run dev -- --host ${frontendHost} --port ${frontendPort} --strictPort`,
      cwd: frontendDirectory,
      url: `${frontendUrl}/`,
      timeout: 60_000,
      reuseExistingServer: false,
      env: { ...process.env, VITE_API_URL: 'http://127.0.0.1:5000/api' },
    },
  ],
  use: {
    baseURL: frontendUrl,
    browserName: 'chromium',
    channel: 'chrome',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  outputDir: outputDirectory,
  timeout: 90_000,
  expect: { timeout: 12_000 },
})
