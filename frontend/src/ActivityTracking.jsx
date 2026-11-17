import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { Activity, Bike, Dumbbell, Flame, Footprints, Pencil, Plus, Target, Timer, Trash2 } from 'lucide-react'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { createFitness, deleteFitness, getActivity, getFitness, getSummary, saveDailyStepGoal, updateFitness } from './services/api'
import { beginSubmission, finishSubmission } from './submissionGuard'

const enter = { initial: { opacity: 0, y: 8 }, animate: { opacity: 1, y: 0 }, transition: { duration: .25 } }
const today = () => {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}
const daysAgo = count => {
  const day = new Date(`${today()}T12:00:00`)
  day.setDate(day.getDate() - count)
  return `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`
}
const blankForm = (record_type = 'daily') => ({
  record_type, record_date: today(), steps: '', activity_type: 'walking', distance: '',
  workout_category: 'strength_training', workout_name: '', workout_minutes: '', calories_burned: '', notes: '',
})
const activityNames = { walking: 'Walking', running: 'Running', jogging: 'Jogging', cycling: 'Cycling' }
const workoutNames = { strength_training: 'Strength training', cardio: 'Cardio', calisthenics: 'Calisthenics', yoga: 'Yoga', other: 'Other' }
const finiteNumber = value => {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function Empty({ title, copy }) {
  return <div className="empty-state"><span><Activity size={20} /></span><b>{title}</b><p>{copy}</p></div>
}

function Metric({ icon: Icon, label, value, unit = '', note = '' }) {
  return <article className="stat-card"><div className="stat-top"><span className="stat-icon lime"><Icon size={17} /></span><span className="stat-kicker">{label}</span></div><div className="stat-value">{value}<small>{unit}</small></div><div className="stat-foot">{note}</div></article>
}

function ActivityName({ row }) {
  if (row.record_type === 'cardio') return activityNames[row.activity_type] || 'Cardio activity'
  if (row.record_type === 'workout') return row.workout_name || 'Workout'
  return 'Daily steps'
}

export default function ActivityTracking({ notify }) {
  const [form, setForm] = useState(blankForm())
  const [editingId, setEditingId] = useState(null)
  const [range, setRange] = useState({ start: daysAgo(6), end: today() })
  const [records, setRecords] = useState([])
  const [weekly, setWeekly] = useState([])
  const [summary, setSummary] = useState(null)
  const [stepGoal, setStepGoal] = useState('')
  const [savingGoal, setSavingGoal] = useState(false)
  const [trend, setTrend] = useState('steps')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const submissionLock = useRef(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    const results = await Promise.allSettled([
      getSummary(), getActivity('week'), getFitness(range),
    ])
    const failures = []
    const [summaryResult, weeklyResult, recordsResult] = results

    if (summaryResult.status === 'fulfilled') {
      const data = summaryResult.value?.data
      const validSummary = data && typeof data === 'object' && !Array.isArray(data)
      setSummary(validSummary ? data : null)
      setStepGoal(validSummary && data.daily_step_goal != null ? String(data.daily_step_goal) : '')
      if (!validSummary) failures.push('The activity summary response was unavailable.')
    } else {
      failures.push(summaryResult.reason?.message || 'Could not load the activity summary.')
      setSummary(null)
    }

    if (weeklyResult.status === 'fulfilled') {
      const data = weeklyResult.value?.data
      setWeekly(Array.isArray(data) ? data.filter(row => row && typeof row === 'object' && !Array.isArray(row)) : [])
      if (data != null && !Array.isArray(data)) failures.push('The weekly activity response was invalid.')
    } else {
      failures.push(weeklyResult.reason?.message || 'Could not load the weekly activity trend.')
      setWeekly([])
    }

    if (recordsResult.status === 'fulfilled') {
      const data = recordsResult.value?.data
      setRecords(Array.isArray(data) ? data.filter(row => row && typeof row === 'object' && !Array.isArray(row)) : [])
      if (data != null && !Array.isArray(data)) failures.push('The activity history response was invalid.')
    } else {
      failures.push(recordsResult.reason?.message || 'Could not load activity history.')
      setRecords([])
    }

    const message = failures.join(' ')
    setError(message)
    setLoading(false)
  }, [range])

  useEffect(() => { load() }, [load])

  const weeklyTotals = useMemo(() => weekly.reduce((totals, row) => ({
    steps: totals.steps + finiteNumber(row.steps),
    distance: totals.distance + finiteNumber(row.cardio_distance_km),
    minutes: totals.minutes + finiteNumber(row.workout_minutes),
    calories: totals.calories + finiteNumber(row.calories_burned),
  }), { steps: 0, distance: 0, minutes: 0, calories: 0 }), [weekly])

  const chartRows = useMemo(() => weekly.filter(row => typeof row.record_date === 'string' && !Number.isNaN(new Date(`${row.record_date}T12:00:00`).getTime())).map(row => ({
    ...row,
    steps: finiteNumber(row.steps),
    cardio_distance_km: finiteNumber(row.cardio_distance_km),
    workout_minutes: finiteNumber(row.workout_minutes),
    day: new Date(`${row.record_date}T12:00:00`).toLocaleDateString('en', { weekday: 'short' }),
  })), [weekly])
  const steps = summary?.steps_today == null ? null : finiteNumber(summary.steps_today)
  const goal = summary?.daily_step_goal
  const completion = summary?.step_goal_percentage
  const recentWorkouts = records.filter(row => row.record_type === 'workout').slice(0, 4)

  const changeType = record_type => {
    setForm({ ...blankForm(record_type), record_date: form.record_date })
    setEditingId(null)
  }
  const change = event => setForm(current => ({ ...current, [event.target.name]: event.target.value }))
  const cancelEdit = () => { setEditingId(null); setForm(blankForm()) }

  const submit = async event => {
    event.preventDefault()
    if (!beginSubmission(submissionLock)) return
    setBusy(true)
    setError('')
    const payload = {
      ...form,
      steps: form.steps === '' ? null : Number(form.steps),
      distance: form.distance === '' ? null : Number(form.distance),
      workout_minutes: form.workout_minutes === '' ? null : Number(form.workout_minutes),
      calories_burned: form.calories_burned === '' ? null : Number(form.calories_burned),
    }
    try {
      if (editingId) {
        await updateFitness(editingId, payload)
        notify?.('Activity record updated')
      } else {
        await createFitness(payload)
        notify?.('Activity record saved')
      }
      cancelEdit()
      await load()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      finishSubmission(submissionLock)
      setBusy(false)
    }
  }

  const edit = row => {
    setEditingId(row.record_id)
    setForm({
      ...blankForm(row.record_type), record_date: row.record_date,
      steps: row.steps == null ? '' : String(row.steps),
      activity_type: row.activity_type || 'walking', distance: row.distance == null ? '' : String(row.distance),
      workout_category: row.workout_category || 'strength_training', workout_name: row.workout_name || '',
      workout_minutes: row.workout_minutes == null ? '' : String(row.workout_minutes),
      calories_burned: row.calories_burned == null ? '' : String(row.calories_burned), notes: row.notes || '',
    })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const remove = async row => {
    if (!window.confirm(`Delete ${row.record_type === 'workout' ? row.workout_name || 'this workout' : ActivityName({ row })}?`)) return
    if (!beginSubmission(submissionLock)) return
    setBusy(true)
    setError('')
    try {
      await deleteFitness(row.record_id)
      notify?.('Activity record deleted')
      if (editingId === row.record_id) cancelEdit()
      await load()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      finishSubmission(submissionLock)
      setBusy(false)
    }
  }

  const saveGoal = async event => {
    event.preventDefault()
    if (!beginSubmission(submissionLock)) return
    setSavingGoal(true)
    setError('')
    try {
      await saveDailyStepGoal(Number(stepGoal))
      notify?.('Daily step goal saved')
      await load()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      finishSubmission(submissionLock)
      setSavingGoal(false)
    }
  }

  const trendOptions = {
    steps: ['steps', 'Steps', '#34D399'],
    distance: ['cardio_distance_km', 'Cardio distance', '#82c4d9'],
    duration: ['workout_minutes', 'Exercise minutes', '#c8a6ea'],
  }
  const [trendKey, trendLabel, trendColor] = trendOptions[trend]

  return <div className="page-wrap activity-page">
    <div className="page-heading" {...enter}><div><span className="eyebrow">YOUR DAILY MOVEMENT</span><h1>Activity Tracking</h1><p>Manually record daily steps, cardio sessions and workouts. FitTrack does not detect activity automatically.</p></div></div>

    {error && <div className="form-error page-error" role="alert">{error} <button className="text-link" onClick={load}>Try again</button></div>}
    {loading && <div className="loading-panel"><span className="spinner" /> Loading activity records…</div>}
    {!loading && <>
      <section className="activity-overview">
        <article className="panel step-progress-panel">
          <div className="panel-heading"><div><span className="muted-label">TODAY</span><h2>Steps versus goal</h2></div><span className="stat-icon lime"><Footprints size={17} /></span></div>
          <div className="step-count"><strong>{steps == null || !Number.isFinite(steps) ? '—' : steps.toLocaleString()}</strong><span>steps completed</span></div>
          {goal == null ? <p className="activity-note">Set a daily step goal to see remaining steps and completion.</p> : <>
            <div className="step-track" role="progressbar" aria-label="Daily step goal progress" aria-valuenow={Math.min(Number(completion || 0), 100)} aria-valuemin="0" aria-valuemax="100"><span style={{ width: `${Math.min(Number(completion || 0), 100)}%` }} /></div>
            <div className="step-progress-meta"><span>{summary?.step_goal_percentage == null ? '—' : `${Number(completion).toLocaleString()}% complete`}</span><span>{summary?.steps_remaining == null ? '— remaining' : `${Number(summary.steps_remaining).toLocaleString()} remaining`} · goal {Number(goal).toLocaleString()}</span></div>
          </>}
          <form className="step-goal-form" onSubmit={saveGoal}><label htmlFor="daily-step-goal">Daily step goal</label><input id="daily-step-goal" type="number" min="1" max="100000" step="1" value={stepGoal} onChange={event => setStepGoal(event.target.value)} placeholder="Set your goal" required/><button className="button button-primary" disabled={savingGoal || !stepGoal}>{savingGoal ? 'Saving…' : 'Save goal'}</button></form>
        </article>
        <div className="stats-grid activity-stats">
          <Metric icon={Footprints} label="THIS WEEK · STEPS" value={weeklyTotals.steps.toLocaleString()} note="Daily records over the last 7 days" />
          <Metric icon={Bike} label="THIS WEEK · CARDIO" value={weeklyTotals.distance.toFixed(1)} unit=" km" note="Walking, running, jogging and cycling" />
          <Metric icon={Timer} label="THIS WEEK · DURATION" value={weeklyTotals.minutes.toLocaleString()} unit=" min" note="Recorded exercise time" />
          <Metric icon={Flame} label="THIS WEEK · EXERCISE" value={Math.round(weeklyTotals.calories).toLocaleString()} unit=" kcal" note="Manually recorded; no calorie estimates" />
        </div>
      </section>

      <section className="activity-content-grid">
        <motion.section className="panel editor-panel activity-editor" {...enter}>
          <div className="panel-heading"><div><span className="muted-label">{editingId ? 'EDIT RECORD' : 'NEW ENTRY'}</span><h2>{editingId ? 'Update activity' : 'Log activity'}</h2></div><span className="stat-icon lime">{form.record_type === 'workout' ? <Dumbbell size={17} /> : <Activity size={17} />}</span></div>
          <form className="form-stack personal-form activity-form" onSubmit={submit}>
            <label>Record type<select value={form.record_type} onChange={event => changeType(event.target.value)} disabled={Boolean(editingId)}><option value="daily">Daily steps</option><option value="cardio">Walking / running / cycling</option><option value="workout">Workout</option></select></label>
            <label>Activity date<input name="record_date" type="date" max={today()} value={form.record_date} onChange={change} required /></label>
            {form.record_type === 'daily' && <label>Steps<input name="steps" type="number" min="0" max="200000" step="1" value={form.steps} onChange={change} placeholder="e.g. 8400" required /></label>}
            {form.record_type === 'cardio' && <>
              <label>Activity<select name="activity_type" value={form.activity_type} onChange={change}><option value="walking">Walking</option><option value="running">Running</option><option value="jogging">Jogging</option><option value="cycling">Cycling</option></select></label>
              <div className="form-row"><label>Distance <i>km</i><input name="distance" type="number" min="0.01" max="1000" step="0.01" value={form.distance} onChange={change} placeholder="e.g. 5.2" required /></label><label>Duration <i>minutes</i><input name="workout_minutes" type="number" min="1" max="1440" step="1" value={form.workout_minutes} onChange={change} placeholder="e.g. 45" required /></label></div>
            </>}
            {form.record_type === 'workout' && <>
              <label>Workout category<select name="workout_category" value={form.workout_category} onChange={change}><option value="strength_training">Strength training</option><option value="cardio">Cardio</option><option value="calisthenics">Calisthenics</option><option value="yoga">Yoga</option><option value="other">Other</option></select></label>
              <label>Workout name<input name="workout_name" type="text" maxLength="120" value={form.workout_name} onChange={change} placeholder="e.g. Upper body session" required /></label>
              <label>Duration <i>minutes</i><input name="workout_minutes" type="number" min="1" max="1440" step="1" value={form.workout_minutes} onChange={change} placeholder="e.g. 45" required /></label>
            </>}
            {form.record_type !== 'daily' && <label>Calories burned <i>optional, enter only when known</i><input name="calories_burned" type="number" min="0" max="10000" step="0.1" value={form.calories_burned} onChange={change} placeholder="Leave blank if unknown" /></label>}
            <label>Notes <i>optional</i><textarea name="notes" maxLength="500" rows="3" value={form.notes} onChange={change} placeholder="Add details about this activity" /></label>
            {form.record_type !== 'daily' && <p className="activity-note">Calories are optional and manually entered. FitTrack does not estimate exercise calories.</p>}
            <div className="privacy-inline"><Target size={15} /> Activity records are saved to your account.</div>
            <button className="button button-primary form-submit" disabled={busy}>{busy ? 'Saving…' : <><Plus size={15} /> {editingId ? 'Save changes' : 'Save activity'}</>}</button>
            {editingId && <button type="button" className="button button-ghost form-submit" onClick={cancelEdit}>Cancel edit</button>}
          </form>
        </motion.section>

        <div className="activity-main-column">
          <section className="panel activity-trend-panel">
            <div className="panel-heading"><div><span className="muted-label">LAST 7 DAYS</span><h2>Weekly activity trend</h2></div><select aria-label="Trend measure" value={trend} onChange={event => setTrend(event.target.value)}><option value="steps">Steps</option><option value="distance">Cardio distance</option><option value="duration">Exercise minutes</option></select></div>
            {chartRows.length ? <div className="chart activity-chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={chartRows} margin={{ left: -20, right: 8, top: 12, bottom: 0 }}><defs><linearGradient id="activityTrend" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={trendColor} stopOpacity={.22} /><stop offset="100%" stopColor={trendColor} stopOpacity={0} /></linearGradient></defs><CartesianGrid stroke="#222a25" vertical={false} /><XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fill: '#79827b', fontSize: 11 }} /><YAxis axisLine={false} tickLine={false} tick={{ fill: '#79827b', fontSize: 10 }} /><Tooltip contentStyle={{ background: '#171d19', border: '1px solid #2b352d', borderRadius: 10, color: '#eef2e9' }} formatter={value => [Number(value).toLocaleString(), trendLabel]} /><Area dataKey={trendKey} type="monotone" stroke={trendColor} strokeWidth={2.5} fill="url(#activityTrend)" /></AreaChart></ResponsiveContainer></div> : <Empty title="No activity this week" copy="Your weekly trend will appear after you record activity." />}
          </section>

          <section className="panel activity-history-panel">
            <div className="panel-heading"><div><span className="muted-label">FILTERED HISTORY</span><h2>Activity records</h2></div><span className="stat-kicker">{records.length} {records.length === 1 ? 'RECORD' : 'RECORDS'}</span></div>
            <div className="filter-bar activity-filter"><label>From<input type="date" value={range.start} onChange={event => setRange(current => ({ ...current, start: event.target.value }))} /></label><label>To<input type="date" value={range.end} onChange={event => setRange(current => ({ ...current, end: event.target.value }))} /></label><button className="text-link" onClick={() => setRange({ start: '', end: '' })}>All dates</button></div>
            {records.length ? <div className="activity-record-list">{records.map((row, index) => <article className="activity-record" key={row.record_id ?? `${row.record_date || 'activity'}-${index}`}>
              <div className="activity-record-main"><b>{ActivityName({ row })}</b><span>{typeof row.record_date === 'string' && !Number.isNaN(new Date(`${row.record_date}T12:00:00`).getTime()) ? new Date(`${row.record_date}T12:00:00`).toLocaleDateString('en', { month: 'short', day: 'numeric', year: 'numeric' }) : 'Date unavailable'}{row.workout_category ? ` · ${workoutNames[row.workout_category] || row.workout_category}` : ''}</span>
                <small>{row.record_type === 'daily' ? `${Number(row.steps || 0).toLocaleString()} steps` : `${row.workout_minutes ?? '—'} min`}{row.distance != null && Number.isFinite(Number(row.distance)) ? ` · ${Number(row.distance).toFixed(2)} km` : ''}{row.calories_burned != null && Number.isFinite(Number(row.calories_burned)) ? ` · ${Math.round(Number(row.calories_burned))} kcal recorded` : ''}{row.average_pace_min_per_km != null && Number.isFinite(Number(row.average_pace_min_per_km)) ? ` · ${Number(row.average_pace_min_per_km).toFixed(2)} min/km` : ''}{row.average_speed_kmh != null && Number.isFinite(Number(row.average_speed_kmh)) ? ` · ${Number(row.average_speed_kmh).toFixed(2)} km/h` : ''}</small>
                {row.notes && <small className="activity-record-notes">{row.notes}</small>}
              </div><div className="activity-record-actions"><button className="icon-button" aria-label={`Edit ${ActivityName({ row })}`} disabled={busy} onClick={() => edit(row)}><Pencil size={14} /></button><button className="icon-button danger" aria-label={`Delete ${ActivityName({ row })}`} disabled={busy} onClick={() => remove(row)}><Trash2 size={14} /></button></div>
            </article>)}</div> : <Empty title="No activity in this date range" copy="Adjust the dates or add an activity record." />}
          </section>

          <section className="panel recent-workouts-panel"><div className="panel-heading"><div><span className="muted-label">THIS DATE RANGE</span><h2>Recent workouts</h2></div><span className="stat-icon lime"><Dumbbell size={17} /></span></div>
            {recentWorkouts.length ? <div className="recent-workout-list">{recentWorkouts.map(row => <div key={row.record_id}><b>{row.workout_name}</b><span>{workoutNames[row.workout_category] || 'Workout'} · {row.workout_minutes} min · {row.record_date}</span></div>)}</div> : <Empty title="No workouts recorded" copy="Workout entries will appear here when you log them." />}
          </section>
        </div>
      </section>
    </>}
  </div>
}
