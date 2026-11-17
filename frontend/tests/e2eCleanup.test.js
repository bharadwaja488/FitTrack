import test from 'node:test'
import assert from 'node:assert/strict'
import { cleanupWithoutMaskingJourneyFailure, resolvePythonExecutable } from '../e2e/cleanupLifecycle.js'
import path from 'node:path'

test('cleanup runs after a failed browser journey and preserves the original failure', async () => {
  const original = new Error('browser assertion failed')
  const cleanupError = new Error('cleanup failed')
  let cleanupCalls = 0
  let reported

  await assert.rejects(
    cleanupWithoutMaskingJourneyFailure(original, async () => {
      cleanupCalls += 1
      throw cleanupError
    }, async error => { reported = error }),
    error => error === original,
  )
  assert.equal(cleanupCalls, 1)
  assert.equal(reported, cleanupError)
})

test('cleanup report failure cannot mask the original browser failure', async () => {
  const original = new Error('browser assertion failed')
  const cleanupError = new Error('cleanup failed')

  await assert.rejects(
    cleanupWithoutMaskingJourneyFailure(original, async () => { throw cleanupError }, async () => {
      throw new Error('attachment failed')
    }),
    error => error === original,
  )
})

test('cleanup failure fails a passing journey and is reported', async () => {
  const cleanupError = new Error('cleanup failed')
  let reported
  await assert.rejects(
    cleanupWithoutMaskingJourneyFailure(null, async () => { throw cleanupError }, async error => { reported = error }),
    error => error === cleanupError,
  )
  assert.equal(reported, cleanupError)
})

test('default cleanup Python path is absolute under the project root', () => {
  const root = path.resolve('E:/My_Projects/FitTrack')
  const resolved = resolvePythonExecutable(root, undefined, candidate => candidate.endsWith('.venv/Scripts/python.exe') || candidate.endsWith('.venv\\Scripts\\python.exe'))
  assert.equal(path.isAbsolute(resolved), true)
  assert.equal(resolved, path.resolve(root, '.venv', 'Scripts', 'python.exe'))
})

test('cleanup Python override is resolved and validated', () => {
  const root = path.resolve('E:/My_Projects/FitTrack')
  const override = path.resolve(root, 'tools', 'python.exe')
  assert.equal(resolvePythonExecutable(root, override, candidate => candidate === override), override)
  assert.throws(() => resolvePythonExecutable(root, 'missing/python.exe', () => false), /does not exist/)
})
