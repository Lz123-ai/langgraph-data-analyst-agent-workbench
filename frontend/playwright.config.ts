import { defineConfig } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const python = process.env.E2E_PYTHON ?? (process.platform === 'win32' ? path.join(root, '.venv', 'Scripts', 'python.exe') : 'python')

export default defineConfig({
  testDir: './e2e',
  timeout: 45_000,
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'retain-on-failure'
  },
  webServer: [
    {
      command: `"${python}" -m uvicorn app.main:app --host 127.0.0.1 --port 8000`,
      cwd: path.join(root, 'backend'),
      url: 'http://127.0.0.1:8000/api/health',
      reuseExistingServer: !process.env.CI
    },
    {
      command: 'npm run dev',
      cwd: path.join(root, 'frontend'),
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: !process.env.CI
    }
  ]
})
