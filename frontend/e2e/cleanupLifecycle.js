import path from 'node:path'
import { statSync } from 'node:fs'

export function resolvePythonExecutable(projectRoot, override, isFile = candidate => {
  try { return statSync(candidate).isFile() } catch { return false }
}) {
  const candidate = override
    ? path.resolve(projectRoot, override)
    : path.resolve(projectRoot, '.venv', 'Scripts', 'python.exe')
  if (!isFile(candidate)) {
    throw new Error('Configured E2E Python executable does not exist or is not a file.')
  }
  return candidate
}

export async function cleanupWithoutMaskingJourneyFailure(journeyFailure, cleanup, reportCleanupFailure) {
  let cleanupFailure
  try {
    await cleanup()
  } catch (error) {
    cleanupFailure = error
    // A reporting/attachment failure must not replace the browser assertion
    // that caused cleanup to run. Keep the cleanup error as the independent
    // failure when the browser journey itself succeeded.
    try { await reportCleanupFailure(error) } catch { /* preserve primary failure */ }
  }
  if (journeyFailure) throw journeyFailure
  if (cleanupFailure) throw cleanupFailure
}
