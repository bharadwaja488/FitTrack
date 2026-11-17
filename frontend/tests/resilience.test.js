import test from 'node:test'
import assert from 'node:assert/strict'
import ErrorBoundary from '../src/ErrorBoundary.js'
import { shouldClearAuthentication, toApiError } from '../src/apiErrors.js'
import { finiteDisplay, isIsoDate, isRecordArray, loadDashboardSection } from '../src/dashboardSections.js'
import { beginSubmission, finishSubmission } from '../src/submissionGuard.js'

function findElement(element, type) {
  if (!element || typeof element !== 'object') return null
  if (element.type === type) return element
  const children = Array.isArray(element.props?.children) ? element.props.children : [element.props?.children]
  for (const child of children) {
    const found = findElement(child, type)
    if (found) return found
  }
  return null
}

test('error boundary switches to a generic fallback and provides a render retry', () => {
  assert.deepEqual(ErrorBoundary.getDerivedStateFromError(new Error('private token value')), { hasError: true })
  const boundary = new ErrorBoundary({ children: 'application' })
  boundary.state = { hasError: true }
  boundary.setState = update => { boundary.state = { ...boundary.state, ...update } }
  const fallback = boundary.render()
  assert.equal(fallback.props.role, 'alert')
  assert.match(fallback.props['aria-labelledby'], /render-error-title/)
  assert.equal(findElement(fallback, 'h1')?.props.children, 'FitTrack hit a rendering problem')
  findElement(fallback, 'button').props.onClick()
  assert.equal(boundary.state.hasError, false)
})

test('error boundary diagnostics omit exception messages and values', () => {
  const boundary = new ErrorBoundary({ children: null })
  const original = console.error
  let logged
  console.error = (...args) => { logged = args }
  try {
    boundary.componentDidCatch(new Error('secret account value'), { componentStack: '\n    in Dashboard' })
  } finally {
    console.error = original
  }
  assert.equal(logged[0], '[FitTrack] React rendering failure')
  assert.deepEqual(logged[1], { errorName: 'Error', componentStack: '\n    in Dashboard' })
})

test('dashboard sections resolve independently and failed-section retry is read-only', async () => {
  let retryCount = 0
  const [summary, chart, recent, goal] = await Promise.all([
    loadDashboardSection(async () => ({ data: { steps: 1200 } }), value => Boolean(value), 'Summary unavailable'),
    loadDashboardSection(async () => { throw new Error('Chart unavailable') }, value => Array.isArray(value), 'Chart unavailable'),
    loadDashboardSection(async () => ({ data: [{ record_id: 8 }] }), isRecordArray, 'Recent activity unavailable'),
    loadDashboardSection(async () => ({ data: { goal: null } }), value => Boolean(value), 'Goal unavailable'),
  ])
  assert.deepEqual(summary.data, { steps: 1200 })
  assert.equal(chart.data, null)
  assert.equal(chart.error, 'Chart unavailable')
  assert.deepEqual(recent.data, [{ record_id: 8 }])
  assert.deepEqual(goal.data, { goal: null })

  const retry = await loadDashboardSection(async () => { retryCount += 1; return { data: [] } }, Array.isArray, 'Chart unavailable')
  assert.deepEqual(retry.data, [])
  assert.equal(retryCount, 1)
})

test('dashboard response guards do not accept fabricated or invalid values', () => {
  assert.equal(finiteDisplay(null), '—')
  assert.equal(finiteDisplay('not-a-number'), '—')
  assert.equal(finiteDisplay(1234.5), '1,235')
  assert.equal(finiteDisplay(2.345, 1), '2.3')
  assert.equal(isIsoDate('2026-11-15'), true)
  assert.equal(isIsoDate('2026-02-30'), false)
  assert.equal(isRecordArray([null]), false)
})

test('API errors map common statuses without exposing server failures', () => {
  const error = (status, message) => ({ response: { status, data: { error: { message } } } })
  assert.equal(toApiError(error(401, 'Bad credentials'), '/auth/login').message, 'Bad credentials')
  assert.equal(toApiError(error(401, 'private detail'), '/profile').message, 'Your session has expired. Please log in again.')
  assert.equal(toApiError(error(403, 'hidden'), '/profile').status, 403)
  assert.match(toApiError(error(404, 'hidden'), '/fitness/1').message, /could not be found/)
  assert.equal(toApiError(error(422, 'Weight is invalid.'), '/weight').message, 'Weight is invalid.')
  assert.match(toApiError(error(429, 'hidden'), '/login').message, /Too many requests/)
  const serverError = toApiError(error(500, 'database password leaked'), '/dashboard')
  assert.equal(serverError.message.includes('database password'), false)
  assert.equal(toApiError({ code: 'ERR_NETWORK' }).message, 'Unable to reach FitTrack. Check your connection and try again.')
  assert.match(toApiError({ code: 'ETIMEDOUT' }).message, /did not respond in time/)
})

test('401 handling clears an invalid session but preserves failed-login form state', () => {
  assert.equal(shouldClearAuthentication(401, '/profile'), true)
  assert.equal(shouldClearAuthentication(401, '/auth/me'), true)
  assert.equal(shouldClearAuthentication(401, '/auth/login'), false)
  assert.equal(shouldClearAuthentication(403, '/profile'), false)
})

test('submission lock allows one mutation until its request finishes', () => {
  const lock = { current: false }
  assert.equal(beginSubmission(lock), true)
  assert.equal(beginSubmission(lock), false)
  finishSubmission(lock)
  assert.equal(beginSubmission(lock), true)
})
