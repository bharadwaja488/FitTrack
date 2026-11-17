import { test, expect } from '@playwright/test'
import { randomUUID } from 'node:crypto'
import { spawnSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { cleanupWithoutMaskingJourneyFailure, resolvePythonExecutable } from './cleanupLifecycle.js'

const projectRoot = fileURLToPath(new URL('../..', import.meta.url))
const backendDirectory = path.resolve(projectRoot, 'backend')
const password = `FitTrackE2e${randomUUID()}Aa9!`
const email = `fittrack-e2e-${randomUUID()}@example.com`
const localDate = new Date()
const today = `${localDate.getFullYear()}-${String(localDate.getMonth() + 1).padStart(2, '0')}-${String(localDate.getDate()).padStart(2, '0')}`
const diagnostics = { consoleErrors: [], failedRequests: [], httpErrors: [] }
const e2eProfile = Object.freeze({ age: 31, gender: 'female', heightM: 1.66, weightKg: 62, activityLevel: 'moderate' })
const e2eBmr = (10 * e2eProfile.weightKg)
  + (6.25 * e2eProfile.heightM * 100)
  - (5 * e2eProfile.age)
  + (e2eProfile.gender === 'male' ? 5 : -161)
const expectedHealthMetrics = {
  bmi: (e2eProfile.weightKg / (e2eProfile.heightM ** 2)).toFixed(1),
  bmr: Math.round(e2eBmr).toLocaleString('en-US'),
  tdee: Math.round(e2eBmr * 1.55).toLocaleString('en-US'),
}

// The guidance is concatenated directly after "Password" in the input's
// accessible name, without whitespace. Match that accessible-name prefix.
const passwordField = page => page.getByRole('textbox', { name: /^Password/ })
const confirmPasswordField = page => page.getByRole('textbox', { name: 'Confirm password', exact: true })

function redactCleanupOutput(value) {
  if (value == null) return ''
  let safe = String(value)
  for (const secret of [process.env.FITTRACK_TEST_DB_PASSWORD, password].filter(Boolean)) {
    safe = safe.split(secret).join('[REDACTED]')
  }
  return safe.replace(/(password|secret|token|cookie)(\s*[=:]\s*)[^\s,;]+/gi, '$1$2[REDACTED]')
}

async function cleanupAccount() {
  const python = resolvePythonExecutable(projectRoot, process.env.FITTRACK_E2E_PYTHON)
  const cleanup = spawnSync(python, [
    path.resolve(backendDirectory, 'tests', 'e2e_cleanup_account.py'), email,
  ], {
    cwd: backendDirectory,
    env: { ...process.env, FITTRACK_E2E_ACCOUNT_PASSWORD: password },
    encoding: 'utf8',
  })
  if (cleanup.status !== 0) {
    const details = {
      status: cleanup.status,
      error: redactCleanupOutput(cleanup.error?.message),
      stdout: redactCleanupOutput(cleanup.stdout),
      stderr: redactCleanupOutput(cleanup.stderr),
    }
    throw new Error(`Disposable E2E account cleanup failed: ${JSON.stringify(details)}`)
  }
}

test('complete disposable account journey and responsive checkpoints', async ({ page }, testInfo) => {
  page.on('console', message => {
    if (message.type() === 'error') diagnostics.consoleErrors.push(message.text())
  })
  page.on('requestfailed', request => diagnostics.failedRequests.push({
    url: request.url(), error: request.failure()?.errorText,
  }))
  page.on('response', response => {
    if (response.status() >= 400) diagnostics.httpErrors.push({
      url: response.url(), method: response.request().method(),
      status: response.status(), statusText: response.statusText(),
    })
  })

  let journeyFailure
  try {
    await page.goto('/signup')
    expect(
      diagnostics.httpErrors.filter(error => error.status === 404 && /favicon/i.test(error.url)),
      'the application favicon should load successfully',
    ).toEqual([])
    await page.getByLabel('Full name').fill('FitTrack E2E User')
    await page.getByLabel('Email address').fill(email)
    await expect(passwordField(page)).toBeVisible()
    await expect(passwordField(page)).toHaveAttribute('minlength', '12')
    await expect(confirmPasswordField(page)).toBeVisible()
    await page.getByRole('button', { name: 'Create account' }).waitFor({ state: 'visible' })
    await passwordField(page).fill(password)
    await confirmPasswordField(page).fill(password)
    await passwordField(page).fill('short')
    await page.getByRole('button', { name: /Create account/ }).click()
    await expect(page).toHaveURL(/\/signup$/)
    await passwordField(page).fill(password)
    await page.getByRole('button', { name: /Create account/ }).click()
    await expect(page).toHaveURL(/\/login$/)
    await page.screenshot({ path: testInfo.outputPath('signup-success.png'), fullPage: true })

    await page.goto('/signup')
    await page.getByLabel('Full name').fill('Duplicate Should Not Create')
    await page.getByLabel('Email address').fill(email)
    await passwordField(page).fill(password)
    await confirmPasswordField(page).fill(password)
    await page.getByRole('button', { name: /Create account/ }).click()
    await expect(page).toHaveURL(/\/login$/)

    await page.getByLabel('Email address').fill(email)
    await passwordField(page).fill(`Wrong${password}`)
    await page.getByRole('button', { name: /Log in/ }).click()
    await expect(page.getByRole('alert')).toBeVisible()
    await passwordField(page).fill(password)
    await page.getByRole('button', { name: /Log in/ }).click()
    await expect(page).toHaveURL(/\/onboarding$/)
    await page.getByLabel('Age').fill(String(e2eProfile.age))
    await page.getByLabel('Gender').selectOption(e2eProfile.gender)
    await page.getByLabel(/Height/).fill(String(e2eProfile.heightM))
    await page.getByLabel(/Weight/).fill(String(e2eProfile.weightKg))
    await page.getByLabel('Typical activity level').selectOption(e2eProfile.activityLevel)
    await page.getByRole('button', { name: /Complete my profile|Save profile/ }).click()
    await expect(page).toHaveURL(/\/app$/)
    await page.screenshot({ path: testInfo.outputPath('dashboard-success.png'), fullPage: true })

    const healthMetricCard = label => page.getByRole('article').filter({
      has: page.getByText(label, { exact: true }),
    })
    const bmiCard = healthMetricCard('BODY MASS INDEX')
    const bmrCard = healthMetricCard('BASAL METABOLIC RATE')
    const tdeeCard = healthMetricCard('DAILY MAINTENANCE')
    await expect(bmiCard).toBeVisible()
    await expect(bmiCard).toContainText(expectedHealthMetrics.bmi)
    await expect(bmrCard).toBeVisible()
    await expect(bmrCard).toContainText(expectedHealthMetrics.bmr)
    await expect(tdeeCard).toBeVisible()
    await expect(tdeeCard).toContainText(expectedHealthMetrics.tdee)

    await page.goto('/app/profile')
    await page.getByLabel('Full name').fill('FitTrack E2E Edited')
    await page.getByRole('button', { name: /Save profile|Update profile/ }).click()
    await expect(page).toHaveURL(/\/app$/)

    await page.goto('/app/goals')
    await page.getByLabel('Goal type').selectOption('weight_loss')
    const targetWeight = page.getByLabel(/Target weight/)
    await targetWeight.fill('55')
    await expect(targetWeight).toHaveValue('55')
    await page.getByLabel(/Daily calorie adjustment/).fill('300')
    await page.getByLabel(/I reviewed and confirm/).check()
    await expect(targetWeight).toHaveValue('55')
    await expect(page.getByLabel(/Daily calorie adjustment/)).toHaveValue('300')
    await expect(page.getByLabel(/I reviewed and confirm/)).toBeChecked()
    const createGoalRequest = page.waitForRequest(request =>
      request.url().endsWith('/api/goals') && request.method() === 'PUT')
    const createGoalResponse = page.waitForResponse(response =>
      response.url().endsWith('/api/goals') && response.request().method() === 'PUT')
    await page.getByRole('button', { name: 'Save goal' }).click()
    const [createRequest, createResponse] = await Promise.all([createGoalRequest, createGoalResponse])
    expect(createRequest.postDataJSON()).toMatchObject({
      goal_type: 'weight_loss', target_weight_kg: 55, calorie_adjustment: 300,
      confirm_calorie_target: true,
    })
    expect(createResponse.status()).toBe(200)
    await expect(page.getByRole('button', { name: 'Update goal' })).toBeVisible()
    await expect(targetWeight).toHaveValue('55')
    await page.reload()
    await expect(page.getByLabel('Goal type')).toHaveValue('weight_loss')
    await expect(page.getByLabel(/Target weight/)).toHaveValue('55')
    await expect(page.getByLabel(/Daily calorie adjustment/)).toHaveValue('300')
    await expect(page.getByLabel(/I reviewed and confirm/)).toBeChecked()
    page.once('dialog', dialog => dialog.accept())
    await page.getByLabel('Goal type').selectOption('maintenance')
    await page.getByLabel(/I reviewed and confirm/).check()
    const updateGoalRequest = page.waitForRequest(request =>
      request.url().endsWith('/api/goals') && request.method() === 'PUT')
    const updateGoalResponse = page.waitForResponse(response =>
      response.url().endsWith('/api/goals') && response.request().method() === 'PUT')
    await page.getByRole('button', { name: 'Update goal' }).click()
    const [updateRequest, updateResponse] = await Promise.all([updateGoalRequest, updateGoalResponse])
    expect(updateRequest.postDataJSON()).toMatchObject({
      goal_type: 'maintenance', target_weight_kg: 62, confirm_calorie_target: true,
    })
    expect(updateResponse.status()).toBe(200)
    await expect(page.getByRole('button', { name: 'Update goal' })).toBeVisible()
    await expect(page.getByLabel('Goal type')).toHaveValue('maintenance')
    await page.reload()
    await expect(page.getByRole('button', { name: 'Update goal' })).toBeVisible()
    await expect(page.getByLabel('Goal type')).toHaveValue('maintenance')
    await expect(page.getByLabel(/Target weight/)).toHaveValue('62')

    // The maintenance target's accessible name also contains "Weight kg";
    // exact matching ensures this is the separate weigh-in form field.
    const weighInInput = page.getByLabel('Weight kg', { exact: true })
    await expect(weighInInput).toHaveCount(1)
    await expect(weighInInput).toBeVisible()
    await weighInInput.fill('61.5')
    await page.getByLabel('Recorded date').fill(today)
    await page.getByRole('button', { name: 'Save weight' }).click()
    const weightRecords = page.locator('.records-panel')
    await expect(weightRecords.getByText('61.50 kg', { exact: true })).toBeVisible()

    await page.goto('/app/activity')
    const recordTypeSelect = page.getByRole('combobox', { name: 'Record type', exact: true })
    await expect(recordTypeSelect).toHaveCount(1)
    const dailyStepGoalInput = page.getByRole('spinbutton', { name: 'Daily step goal', exact: true })
    await expect(dailyStepGoalInput).toHaveCount(1)
    await dailyStepGoalInput.fill('10000')
    const saveStepGoalButton = page.getByRole('button', { name: 'Save goal', exact: true })
    await expect(saveStepGoalButton).toHaveCount(1)
    await saveStepGoalButton.click()
    await expect(page.getByRole('progressbar', { name: 'Daily step goal progress' })).toBeVisible()
    await recordTypeSelect.selectOption('daily')
    const stepsInput = page.getByRole('spinbutton', { name: 'Steps', exact: true })
    await expect(stepsInput).toHaveCount(1)
    await stepsInput.fill('8400')
    const saveActivityButton = page.getByRole('button', { name: 'Save activity', exact: true })
    await expect(saveActivityButton).toHaveCount(1)
    await saveActivityButton.click()
    const activityHistory = page.locator('.activity-history-panel')
    await expect(activityHistory.getByText('8,400 steps', { exact: true })).toBeVisible()

    for (const type of ['walking', 'running', 'jogging', 'cycling']) {
      await recordTypeSelect.selectOption('cardio')
      const activityTypeSelect = page.getByRole('combobox', { name: 'Activity', exact: true })
      await expect(activityTypeSelect).toHaveCount(1)
      await activityTypeSelect.selectOption(type)
      const distanceInput = page.getByRole('spinbutton', { name: 'Distance km', exact: true })
      const cardioDurationInput = page.getByRole('spinbutton', { name: 'Duration minutes', exact: true })
      const caloriesInput = page.getByRole('spinbutton', {
        name: 'Calories burned optional, enter only when known', exact: true,
      })
      await expect(distanceInput).toHaveCount(1)
      await expect(cardioDurationInput).toHaveCount(1)
      await expect(caloriesInput).toHaveCount(1)
      await distanceInput.fill('3.5')
      await cardioDurationInput.fill('25')
      await expect(saveActivityButton).toHaveCount(1)
      await saveActivityButton.click()
      const activityName = type[0].toUpperCase() + type.slice(1)
      await expect(activityHistory.getByText(activityName, { exact: true })).toBeVisible()
      const activityRecord = activityHistory.locator('.activity-record').filter({ hasText: new RegExp(`^${activityName}`) })
      await expect(activityRecord).toHaveCount(1)
      if (type === 'running') {
        const samePaceRows = activityHistory.getByText('25 min · 3.50 km · 7.14 min/km', { exact: true })
        await expect(samePaceRows).toHaveCount(2)
        const walkingRecord = activityHistory.locator('.activity-record').filter({ hasText: /^Walking/ })
        const runningRecord = activityHistory.locator('.activity-record').filter({ hasText: /^Running/ })
        await expect(walkingRecord).toHaveCount(1)
        await expect(runningRecord).toHaveCount(1)
        await expect(walkingRecord.getByText('25 min · 3.50 km · 7.14 min/km', { exact: true })).toHaveCount(1)
        await expect(runningRecord.getByText('25 min · 3.50 km · 7.14 min/km', { exact: true })).toHaveCount(1)
      }
      if (type === 'cycling') {
        await expect(activityRecord.getByText('25 min · 3.50 km · 8.40 km/h', { exact: true })).toHaveCount(1)
      }
    }
    await recordTypeSelect.selectOption('workout')
    const workoutCategorySelect = page.getByRole('combobox', { name: 'Workout category', exact: true })
    await expect(workoutCategorySelect).toHaveCount(1)
    await workoutCategorySelect.selectOption('strength_training')
    const workoutNameInput = page.getByRole('textbox', { name: 'Workout name', exact: true })
    await expect(workoutNameInput).toHaveCount(1)
    await workoutNameInput.fill('E2E Strength Session')
    const workoutDurationInput = page.getByRole('spinbutton', { name: 'Duration minutes', exact: true })
    const workoutCaloriesInput = page.getByRole('spinbutton', {
      name: 'Calories burned optional, enter only when known', exact: true,
    })
    await expect(workoutDurationInput).toHaveCount(1)
    await expect(workoutCaloriesInput).toHaveCount(1)
    await workoutDurationInput.fill('40')
    await expect(saveActivityButton).toHaveCount(1)
    await saveActivityButton.click()
    await expect(activityHistory.getByText('E2E Strength Session', { exact: true })).toBeVisible()
    const editWorkoutButton = activityHistory.getByRole('button', {
      name: 'Edit E2E Strength Session', exact: true,
    })
    await expect(editWorkoutButton).toHaveCount(1)
    await editWorkoutButton.click()
    await expect(workoutNameInput).toHaveCount(1)
    await workoutNameInput.fill('E2E Edited Workout')
    const saveChangesButton = page.getByRole('button', { name: 'Save changes', exact: true })
    await expect(saveChangesButton).toHaveCount(1)
    await saveChangesButton.click()
    await expect(activityHistory.getByText('E2E Edited Workout', { exact: true })).toBeVisible()
    const activityFromDate = activityHistory.getByRole('textbox', { name: 'From', exact: true })
    const activityToDate = activityHistory.getByRole('textbox', { name: 'To', exact: true })
    await expect(activityFromDate).toHaveCount(1)
    await expect(activityToDate).toHaveCount(1)
    await activityFromDate.fill(today)
    await activityToDate.fill(today)
    await expect(activityHistory.getByText('8,400 steps', { exact: true })).toBeVisible()
    await expect(activityHistory.getByText('E2E Edited Workout', { exact: true })).toBeVisible()
    await page.screenshot({ path: testInfo.outputPath('activity-success.png'), fullPage: true })

    await page.goto('/app/history')
    await expect(page.getByRole('heading', { name: 'My History', exact: true })).toBeVisible()
    const historyRecords = page.locator('.records-panel')
    await expect(historyRecords.getByText('E2E Edited Workout', { exact: true })).toBeVisible()
    const fromDate = page.getByRole('textbox', { name: 'From', exact: true })
    const toDate = page.getByRole('textbox', { name: 'To', exact: true })
    await expect(fromDate).toHaveCount(1)
    await expect(toDate).toHaveCount(1)
    await fromDate.fill(today)
    await toDate.fill(today)
    await expect(historyRecords.getByText('E2E Edited Workout', { exact: true })).toBeVisible()
    const clearHistoryButton = page.getByRole('button', { name: 'Clear', exact: true })
    await expect(clearHistoryButton).toHaveCount(1)
    await clearHistoryButton.click()
    await page.goto('/app/settings')
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible()

    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/app/activity')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    await page.setViewportSize({ width: 768, height: 1024 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    await page.setViewportSize({ width: 390, height: 844 })
    await expect(page.getByRole('button', { name: 'Open navigation' })).toBeVisible()
    await page.getByRole('button', { name: 'Open navigation' }).click()
    await expect(page.getByRole('link', { name: 'Activity Tracking' })).toBeVisible()
    await page.getByRole('link', { name: 'Activity Tracking' }).click()
    await expect(page.getByRole('button', { name: 'Close navigation' })).toHaveCount(0)
    await expect(page.getByText('Weekly activity trend')).toBeVisible()
    await expect(recordTypeSelect).toBeVisible()
    await expect(recordTypeSelect).toHaveValue('daily')
    const noOverflow = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)
    expect(noOverflow, 'mobile page should not overflow horizontally').toBe(true)
    expect(await page.evaluate(() => document.documentElement.scrollHeight > window.innerHeight)).toBe(true)
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight))
    await expect(page.getByRole('heading', { name: 'Activity records' })).toBeVisible()
    await page.screenshot({ path: testInfo.outputPath('mobile-activity.png'), fullPage: true })

    await page.reload()
    await expect(page).toHaveURL(/\/app\/activity$/)
    const reloadedActivityHistory = page.locator('.activity-history-panel')
    await expect(reloadedActivityHistory.getByText('E2E Edited Workout', { exact: true })).toBeVisible()
    const dailyStepsRecord = reloadedActivityHistory.locator('.activity-record').filter({ hasText: '8,400 steps' })
    await expect(dailyStepsRecord).toHaveCount(1)
    const deleteDailyStepsButton = dailyStepsRecord.getByRole('button', {
      name: 'Delete Daily steps', exact: true,
    })
    await expect(deleteDailyStepsButton).toHaveCount(1)
    page.once('dialog', dialog => dialog.accept())
    await deleteDailyStepsButton.click()
    await expect(reloadedActivityHistory.getByText('8,400 steps', { exact: true })).toHaveCount(0)
    await page.getByRole('button', { name: 'Open navigation' }).click()
    await page.getByRole('button', { name: 'Log out' }).click()
    await expect(page).toHaveURL(/\/login$/)
    await page.goto('/app')
    await expect(page).toHaveURL(/\/login$/)
    await page.getByLabel('Email address').fill(email)
    await passwordField(page).fill(password)
    await page.getByRole('button', { name: /Log in/ }).click()
    await expect(page).toHaveURL(/\/app$/)

    await page.goto('/app/settings')
    const dangerPanel = page.locator('.danger-panel')
    await dangerPanel.getByLabel('Current password').fill(password)
    await dangerPanel.getByLabel(/Type\s+DELETE\s+to confirm/).fill('DELETE')
    await dangerPanel.getByRole('button', { name: 'Delete my account' }).click()
    await expect(page).toHaveURL(/\/$/)
    await page.goto('/login')
    await page.getByLabel('Email address').fill(email)
    await passwordField(page).fill(password)
    await page.getByRole('button', { name: /Log in/ }).click()
    await expect(page.getByRole('alert')).toBeVisible()
  } catch (error) {
    journeyFailure = error
  } finally {
    try {
      await testInfo.attach('browser-diagnostics.json', {
        body: JSON.stringify(diagnostics, null, 2), contentType: 'application/json',
      })
    } catch (error) {
      console.error(`[FitTrack E2E] browser diagnostics attachment failed: ${redactCleanupOutput(error.message)}`)
    }
  }

  await cleanupWithoutMaskingJourneyFailure(journeyFailure, cleanupAccount, async error => {
    const details = redactCleanupOutput(error.message)
    try {
      await testInfo.attach('cleanup-failure.txt', {
        body: details, contentType: 'text/plain',
      })
    } catch (reportError) {
      console.error(`[FitTrack E2E] cleanup diagnostic attachment failed: ${redactCleanupOutput(reportError.message)}`)
    }
    console.error(`[FitTrack E2E] cleanup failed: ${details}`)
  })
})
