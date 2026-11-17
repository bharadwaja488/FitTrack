import test from 'node:test'
import assert from 'node:assert/strict'
import { createVercelConfig } from '../vercelConfig.js'

test('Vercel proxies the API before applying the SPA fallback', () => {
  const config = createVercelConfig('https://fittrack-api.example.com/')
  assert.deepEqual(config.headers, [{
    source: '/(.*)',
    headers: [
      { key: 'Referrer-Policy', value: 'no-referrer' },
      { key: 'X-Content-Type-Options', value: 'nosniff' },
      { key: 'X-Frame-Options', value: 'DENY' },
      { key: 'Strict-Transport-Security', value: 'max-age=31536000' },
    ],
  }])
  assert.deepEqual(config.rewrites, [
    {
      source: '/api/:path*',
      destination: 'https://fittrack-api.example.com/api/:path*',
    },
    {
      source: '/(.*)',
      destination: '/index.html',
    },
  ])
})

test('Vercel configuration requires a public HTTPS origin without a path', () => {
  for (const invalid of [
    undefined,
    'http://fittrack-api.example.com',
    'https://fittrack-api.example.com/api',
    'https://user:password@fittrack-api.example.com',
    'https://localhost:5000',
    'not a URL',
  ]) {
    assert.throws(() => createVercelConfig(invalid))
  }
})
