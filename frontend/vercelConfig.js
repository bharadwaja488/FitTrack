export function createVercelConfig(renderApiOrigin) {
  if (!renderApiOrigin) {
    throw new Error('Set RENDER_API_ORIGIN to the HTTPS origin of the FitTrack Render service.')
  }

  let apiOrigin
  try {
    const parsed = new URL(renderApiOrigin)
    const hostname = parsed.hostname.toLowerCase()
    if (parsed.protocol !== 'https:' || parsed.username || parsed.password
        || parsed.pathname !== '/' || parsed.search || parsed.hash
        || hostname === 'localhost' || hostname.endsWith('.localhost')) {
      throw new Error('The Render API destination must be a public HTTPS origin only.')
    }
    apiOrigin = parsed.origin
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error('RENDER_API_ORIGIN must be a valid HTTPS origin.')
    }
    throw error
  }

  return {
    headers: [
      {
        source: '/(.*)',
        headers: [
          { key: 'Referrer-Policy', value: 'no-referrer' },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'Strict-Transport-Security', value: 'max-age=31536000' },
        ],
      },
    ],
    rewrites: [
      {
        source: '/api/:path*',
        destination: `${apiOrigin}/api/:path*`,
      },
      {
        source: '/(.*)',
        destination: '/index.html',
      },
    ],
  }
}
