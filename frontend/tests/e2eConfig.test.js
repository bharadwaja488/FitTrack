import test from 'node:test'
import assert from 'node:assert/strict'
import playwrightConfig from '../playwright.config.js'
import viteConfig from '../vite.config.js'

test('Playwright starts FitTrack frontend on the isolated verified port', () => {
  const [backend, frontend] = playwrightConfig.webServer
  assert.equal(frontend.url, 'http://127.0.0.1:5174/')
  assert.match(frontend.command, /--host 127\.0\.0\.1 --port 5174 --strictPort/)
  assert.equal(frontend.reuseExistingServer, false)
  assert.equal(playwrightConfig.use.baseURL, 'http://127.0.0.1:5174')
  assert.equal(viteConfig.server.host, '127.0.0.1')
  assert.equal(viteConfig.server.port, 5174)
  assert.equal(viteConfig.server.strictPort, true)
  assert.equal(frontend.env.VITE_API_URL, 'http://127.0.0.1:5000/api')
  assert.equal(backend.url, 'http://127.0.0.1:5000/api/health')
})

test('E2E backend receives only the approved database identity and matching CORS origins', () => {
  const [backend] = playwrightConfig.webServer
  assert.equal(backend.env.DB_NAME, 'fittrack_test_20261116_a91f')
  assert.equal(backend.env.DB_HOST, '127.0.0.1')
  assert.equal(backend.env.DB_USER, 'ft_test_20261116_a91f')
  assert.equal(backend.env.FRONTEND_URL, 'http://127.0.0.1:5174')
  assert.equal(backend.env.FRONTEND_ORIGINS, 'http://127.0.0.1:5174,http://localhost:5174')
  assert.equal(backend.reuseExistingServer, false)
})
