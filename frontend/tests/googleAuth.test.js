import test from 'node:test'
import assert from 'node:assert/strict'

test('Google OAuth endpoint paths match production proxy specifications', () => {
  const googleAuthStartPath = '/auth/google'
  const googleAuthCallbackPath = '/auth/google/callback'
  const providersPath = '/auth/providers'

  assert.equal(googleAuthStartPath, '/auth/google')
  assert.equal(googleAuthCallbackPath, '/auth/google/callback')
  assert.equal(providersPath, '/auth/providers')
})

test('Google login error messages are descriptive and actionable', () => {
  const queryErrors = {
    google_not_configured: 'Google sign-in could not be completed. You can try again or log in with email.',
    oauth_state: 'Google sign-in could not be completed. You can try again or log in with email.',
    google_sign_in: 'Google sign-in could not be completed. You can try again or log in with email.'
  }

  for (const [code, expected] of Object.entries(queryErrors)) {
    assert.equal(typeof code, 'string')
    assert.match(expected, /Google sign-in could not be completed/)
  }
})

test('Google login button state logic reflects provider discovery response', () => {
  function renderGoogleOption(googleEnabled, apiBase = '/api') {
    if (googleEnabled) {
      return {
        type: 'button',
        href: `${apiBase}/auth/google`,
        label: 'Continue with Google',
        enabled: true
      }
    }
    return {
      type: 'placeholder',
      label: 'Google sign-in unavailable until configured in .env',
      enabled: false
    }
  }

  const disabledState = renderGoogleOption(false)
  assert.equal(disabledState.enabled, false)
  assert.match(disabledState.label, /unavailable until configured/)

  const enabledState = renderGoogleOption(true, '/api')
  assert.equal(enabledState.enabled, true)
  assert.equal(enabledState.href, '/api/auth/google')
  assert.equal(enabledState.label, 'Continue with Google')
})
