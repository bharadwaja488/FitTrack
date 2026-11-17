import { useCallback, useEffect, useRef, useState } from 'react'
import { AnimatePresence, MotionConfig, motion } from 'framer-motion'
import { Activity, ArrowLeft, ArrowRight, ArrowUpRight, Bike, CalendarDays, Check, ChevronRight, CircleUserRound, Dumbbell, Footprints, Flame, Gauge, HeartPulse, History as HistoryIcon, KeyRound, LogOut, Menu, Pencil, Plus, Settings, ShieldCheck, Sparkles, Target, Timer, Trash2, UserRound, X } from 'lucide-react'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Link, Navigate, NavLink, Route, Routes, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { AuthProvider, useAuth } from './AuthContext'
import ActivityTracking from './ActivityTracking'
import { API_BASE, addWeight, authApi, changePassword, createFitness, deleteAccount, deleteWeight, getActivity, getFitness, getGoal, getProfile, getSummary, getWeightHistory, saveGoal, saveProfile, setGoalStatus, updateWeight } from './services/api'
import { finiteDisplay, isIsoDate, isRecord, isRecordArray, loadDashboardSection } from './dashboardSections'
import { beginSubmission, finishSubmission } from './submissionGuard'

const nav = [
  { to: '/app', label: 'Overview', icon: Activity, end: true },
  { to: '/app/profile', label: 'My Profile', icon: CircleUserRound },
  { to: '/app/health', label: 'Health Metrics', icon: HeartPulse },
  { to: '/app/goals', label: 'Goals & Weight', icon: Target },
  { to: '/app/activity', label: 'Activity Tracking', icon: Dumbbell },
  { to: '/app/history', label: 'My History', icon: HistoryIcon },
]
const enter = { initial: { opacity: 0, y: 10 }, animate: { opacity: 1, y: 0 }, transition: { duration: .3 } }
const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}` }

function Toast({ message, close }) { return <AnimatePresence>{message && <motion.div className="toast" initial={{opacity:0,y:12}} animate={{opacity:1,y:0}} exit={{opacity:0,y:12}}><Check size={16}/>{message}<button onClick={close} aria-label="Dismiss"><X size={14}/></button></motion.div>}</AnimatePresence> }
function App() {
  const [toast,setToast]=useState('')
  const notify=message=>{setToast(message);window.setTimeout(()=>setToast(''),3500)}
  return <MotionConfig reducedMotion="user"><AuthProvider><Routes>
    <Route path="/" element={<Landing/>}/>
    <Route path="/signup" element={<Signup notify={notify}/>}/>
    <Route path="/login" element={<Login notify={notify}/>}/>
    <Route path="/forgot-password" element={<ForgotPassword/>}/>
    <Route path="/reset-password" element={<ResetPassword notify={notify}/>}/>
    <Route path="/onboarding" element={<Onboarding notify={notify}/>}/>
    <Route path="/app/*" element={<PrivateLayout notify={notify}/>}/>
    <Route path="*" element={<Navigate to="/" replace/>}/>
  </Routes><Toast message={toast} close={()=>setToast('')}/></AuthProvider></MotionConfig>
}

function Brand({small=false}) { return <Link to="/" className={`brand ${small?'brand-small':''}`}><span className="brand-mark"><Activity size={17}/></span>fittrack</Link> }
function LandingDashboardPreview() {
  return <motion.div className="hero-preview" {...enter}>
    <div className="preview-window">
      <div className="preview-sidebar"><Brand small/><span className="preview-nav active"><Activity size={13}/> Overview</span><span className="preview-nav"><HeartPulse size={13}/> Health</span><span className="preview-nav"><Footprints size={13}/> Activity</span><span className="preview-nav"><HistoryIcon size={13}/> History</span><div className="preview-sidebar-rule"><span/>YOUR TRAINING LOG</div></div>
      <div className="preview-main">
        <div className="preview-topline"><div><span className="muted-label">YOUR PERSONAL SPACE</span><b>Overview</b></div><span className="preview-date"><CalendarDays size={12}/> YOUR RECORDS</span><span className="preview-avatar"><UserRound size={14}/></span></div>
        <div className="preview-welcome"><div><span className="muted-label">HEALTH AT A GLANCE</span><b>Your progress, in focus.</b><small>Your own profile and activity, together.</small></div><span className="preview-secure"><ShieldCheck size={13}/> Private</span></div>
        <div className="preview-metric-grid"><div><Gauge/><small>BMI</small><b>Calculated from your profile</b></div><div><HeartPulse/><small>BMR</small><b>Estimated at rest</b></div><div><Sparkles/><small>TDEE</small><b>Based on activity level</b></div></div>
        <div className="preview-focus-row"><div className="preview-focus-card"><div><span>WEIGHT PROGRESS</span><Target size={14}/></div><strong>— <small>kg</small></strong><p>Goal and weigh-ins in one view</p><div className="preview-rule" aria-hidden="true"/></div><div className="preview-focus-card preview-steps-card"><div><span>DAILY MOVEMENT</span><Footprints size={14}/></div><strong>Steps</strong><p>Track the movement you record</p><div className="preview-steps-marks" aria-hidden="true"/></div></div>
        <div className="preview-chart-card"><div><b>Activity trend</b><span>Real records only</span></div><div className="preview-chart-empty"><Activity size={17}/><span>Your recorded activity will appear here</span></div></div>
      </div>
    </div>
  </motion.div>
}
function Landing() {
  return <div className="landing">
    <nav className="landing-nav"><Brand/><div className="landing-links"><a href="#features">Features</a><a href="#about">About</a><Link to="/login" className="landing-login">Log in</Link><Link to="/signup" className="button button-primary">Get started <ArrowUpRight size={15}/></Link></div></nav>
    <main className="hero">
      <div className="hero-copy"><span className="eyebrow hero-kicker"><span className="live-dot"/> PERSONAL FITNESS TRACKING <span className="hero-kicker-index">01 / 03</span></span><h1>Built for your<br/><span>next mile.</span></h1><p>Understand your health baseline, set a weight direction and keep a clear record of the movement you do.</p><div className="hero-actions"><Link className="button button-primary" to="/signup">Create your account <ArrowRight size={16}/></Link><Link className="button button-ghost" to="/login">I already have an account</Link></div><div className="trust-note"><span className="trust-icon"><ShieldCheck size={13}/></span> Private by design. Your account only sees your data.</div></div>
      <LandingDashboardPreview/>
    </main>
    <section id="features" className="feature-section"><div className="section-intro"><span className="eyebrow">YOUR ROUTINE, CLEARER</span><h2>Everything in one personal space.</h2><p>Your profile, your records, your progress. Kept together and private to your account.</p></div><div className="feature-grid">{[[Footprints,'Track your movement','Log daily steps, distance, workout time and calories.'],[Gauge,'Understand your health','Keep BMI and daily calorie estimates in helpful context.'],[HeartPulse,'Notice your progress','Explore weekly and monthly trends from your own history.']].map(([Icon,title,copy])=><article className="feature-tile" key={title}><Icon size={20}/><h3>{title}</h3><p>{copy}</p></article>)}</div></section>
    <section id="about" className="about-section"><div><span className="eyebrow">BUILT AROUND YOU</span><h2>One account.<br/>A clearer picture.</h2></div><p>FitTrack brings your profile and activity history into one private view, so you can focus on consistent habits and the progress you make.</p></section><footer><Brand small/><span>Your progress, in focus.</span><span>© 2026 FitTrack</span></footer>
  </div>
}

function AuthFrame({title,subtitle,children,back='/'} ) { return <div className="auth-page"><div className="auth-nav"><Brand/><Link to={back} className="auth-back"><ArrowLeft size={14}/> Back</Link></div><motion.main className="auth-card" {...enter}><div className="auth-emblem"><Activity size={20}/></div><div className="auth-title"><span className="eyebrow">YOUR PERSONAL FITNESS SPACE</span><h1>{title}</h1><p>{subtitle}</p></div>{children}<p className="auth-privacy"><ShieldCheck size={14}/> Your account and fitness information stay private.</p></motion.main><div className="auth-copyright">FitTrack · A more personal way to track your fitness</div></div> }
function GoogleOption() { const [enabled,setEnabled]=useState(false); useEffect(()=>{authApi.providers().then(r=>setEnabled(r.data.google_enabled)).catch(()=>{})},[]);return enabled?<a href={`${API_BASE}/auth/google`} className="google-button"><GoogleMark/>Continue with Google</a>:<div className="google-unavailable"><GoogleMark/>Google sign-in unavailable until configured in .env</div> }
function GoogleMark() { return <svg viewBox="0 0 48 48" width="17" height="17" aria-hidden="true"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5Z" transform="translate(0 5)"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.9c-.58 2.96-2.26 5.48-4.76 7.18l7.72 5.99c4.51-4.17 7.12-10.31 7.12-17.64Z"/><path fill="#FBBC05" d="M10.53 28.59A14.4 14.4 0 0 1 9.75 24c0-1.59.27-3.13.76-4.59l-7.98-6.19A23.94 23.94 0 0 0 0 24c0 3.88.93 7.55 2.56 10.78l7.97-6.19Z" transform="translate(0 0)"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.9-5.81l-7.72-5.99c-2.14 1.44-4.88 2.3-8.18 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48Z"/></svg> }
function AuthFields({ mode, notify }) {
  const { authenticate } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ full_name: '', email: '', password: '', confirm_password: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const submissionLock = useRef(false)
  const change = event => setForm(current => ({ ...current, [event.target.name]: event.target.value }))
  const submit = async event => {
    event.preventDefault()
    if (!beginSubmission(submissionLock)) return
    setError('')
    setBusy(true)
    try {
      if (mode === 'signup') {
        const response = await authApi.register(form)
        notify(response.data.message)
        navigate('/login')
        return
      }
      const response = await authApi.login(form)
      authenticate(response.data)
      notify('Welcome back')
      navigate(!response.data.account.has_profile ? '/onboarding' : '/app')
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      finishSubmission(submissionLock)
      setBusy(false)
    }
  }
  return <form className="auth-form" onSubmit={submit}>
    {mode === 'signup' && <label>Full name<input name="full_name" autoComplete="name" value={form.full_name} onChange={change} placeholder="Your name" maxLength="100" required/></label>}
    <label>Email address<input name="email" type="email" autoComplete="email" value={form.email} onChange={change} placeholder="you@example.com" required/></label>
    <label>Password<input name="password" type="password" autoComplete={mode === 'signup' ? 'new-password' : 'current-password'} value={form.password} onChange={change} placeholder={mode === 'signup' ? 'At least 12 characters' : 'Your password'} required minLength={mode === 'signup' ? 12 : 1}/>{mode === 'signup' && <small className="field-note">12+ characters with upper and lowercase letters and a number.</small>}</label>
    {mode === 'signup' && <label>Confirm password<input name="confirm_password" type="password" autoComplete="new-password" value={form.confirm_password} onChange={change} placeholder="Enter your password again" required/></label>}
    {error && <div className="form-error" role="alert" aria-live="assertive">{error}</div>}
    <button className="button button-primary auth-submit" disabled={busy}>{busy ? <><span className="spinner dark"/> Please wait…</> : mode === 'signup' ? 'Create account' : 'Log in'}<ArrowRight size={15}/></button>
    {mode === 'login' && <Link to="/forgot-password" className="forgot-link">Forgot password?</Link>}
  </form>
}
function Signup({notify}) { const {account}=useAuth();if(account)return <Navigate to={account.has_profile?'/app':'/onboarding'} replace/>;return <AuthFrame title="Create your account" subtitle="A private place to understand your fitness progress."><GoogleOption/><div className="auth-divider"><span/>or continue with email<span/></div><AuthFields mode="signup" notify={notify}/><p className="auth-switch">Already have an account? <Link to="/login">Log in</Link></p><p className="terms-note">By creating an account, you agree to use FitTrack responsibly. Health metrics are estimates, not medical advice.</p></AuthFrame> }
function Login({notify}) { const {account}=useAuth();const [search]=useSearchParams();if(account)return <Navigate to={account.has_profile?'/app':'/onboarding'} replace/>;return <AuthFrame title="Welcome back" subtitle="Log in to your personal fitness space.">{search.get('error')&&<div className="form-error">Google sign-in could not be completed. You can try again or log in with email.</div>}<GoogleOption/><div className="auth-divider"><span/>or log in with email<span/></div><AuthFields mode="login" notify={notify}/><p className="auth-switch">New to FitTrack? <Link to="/signup">Create an account</Link></p></AuthFrame> }
function ForgotPassword() { const [email,setEmail]=useState(''),[message,setMessage]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);const submit=async e=>{e.preventDefault();setError('');setBusy(true);try{const r=await authApi.forgot({email});setMessage(r.data.mail_configured?'If the address belongs to an account, reset instructions are on their way.':'Email reset is not configured on this server yet. Configure SMTP in .env to send reset links.')}catch(e){setError(e.message)}finally{setBusy(false)}};return <AuthFrame title="Reset your password" subtitle="We’ll send a private reset link if your account uses that email."><form className="auth-form" onSubmit={submit}><label>Email address<input type="email" autoComplete="email" value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@example.com" required/></label>{message&&<div className="form-success"><Check size={15}/>{message}</div>}{error&&<div className="form-error">{error}</div>}<button className="button button-primary auth-submit" disabled={busy}>{busy?'Sending…':'Send reset link'}<ArrowRight size={15}/></button></form><p className="auth-switch"><Link to="/login">Back to log in</Link></p></AuthFrame> }
function ResetPassword({notify}) { const [params]=useSearchParams(),navigate=useNavigate(),[password,setPassword]=useState(''),[confirm,setConfirm]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);const submit=async e=>{e.preventDefault();setError('');setBusy(true);try{await authApi.reset({token:params.get('token'),password,confirm_password:confirm});notify('Password reset. Log in with your new password.');navigate('/login')}catch(e){setError(e.message)}finally{setBusy(false)}};return <AuthFrame title="Choose a new password" subtitle="Use a strong password you haven’t used elsewhere."><form className="auth-form" onSubmit={submit}><label>New password<input type="password" value={password} onChange={e=>setPassword(e.target.value)} minLength="12" required/></label><label>Confirm new password<input type="password" value={confirm} onChange={e=>setConfirm(e.target.value)} minLength="12" required/></label>{error&&<div className="form-error">{error}</div>}<button className="button button-primary auth-submit" disabled={busy}>{busy?'Updating…':'Reset password'}<ArrowRight size={15}/></button></form></AuthFrame> }

function Protected({children,needsProfile=true}) { const {account,loading,authError,refresh}=useAuth();const location=useLocation();if(loading)return <div className="full-loading"><span className="spinner"/> Restoring your secure session…</div>;if(authError)return <div className="full-loading"><section className="panel"><h2>FitTrack is temporarily unavailable</h2><p>{authError}</p><button className="button button-primary" onClick={refresh}>Try again</button></section></div>;if(!account)return <Navigate to="/login" state={{from:location.pathname}} replace/>;if(needsProfile&&!account.has_profile)return <Navigate to="/onboarding" replace/>;return children }
function Onboarding({notify}) { const {account,loading,refresh}=useAuth();if(loading)return <div className="full-loading"><span className="spinner"/> Loading…</div>;if(!account)return <Navigate to="/signup" replace/>;if(account.has_profile)return <Navigate to="/app" replace/>;return <ProfileEditor onboarding notify={notify} onSaved={async()=>{await refresh()}}/> }
function PrivateLayout({notify}) { return <Protected><PersonalLayout notify={notify}/></Protected> }
function PersonalLayout({notify}) { const {account,signOut}=useAuth(),[drawer,setDrawer]=useState(false),[busy,setBusy]=useState(false),location=useLocation(),navigate=useNavigate();useEffect(()=>setDrawer(false),[location]);const logout=async()=>{setBusy(true);try{await signOut();navigate('/login')}finally{setBusy(false)}};const title=nav.find(n=>n.to===location.pathname)?.label||'Settings';return <div className="app-shell"><AnimatePresence>{drawer&&<motion.button aria-label="Close navigation" className="scrim" onClick={()=>setDrawer(false)} initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}}/>}</AnimatePresence><aside className={`sidebar ${drawer?'sidebar-open':''}`}><Brand/><div className="account-switch"><div className="profile-avatar">{account.full_name?.slice(0,1).toUpperCase()}</div><div><b title={account.full_name}>{account.full_name}</b><small>Personal account</small></div><ShieldCheck size={15}/></div><span className="nav-label">YOUR FITNESS</span><div className="nav-items">{nav.map(item=><NavLink end={item.end} key={item.to} to={item.to} onClick={()=>setDrawer(false)} className={({isActive})=>`nav-item ${isActive?'active':''}`}><item.icon size={17}/>{item.label}</NavLink>)}</div><div className="sidebar-bottom"><NavLink to="/app/settings" onClick={()=>setDrawer(false)} className={({isActive})=>`nav-item ${isActive?'active':''}`}><Settings size={17}/>Settings</NavLink><button className="nav-item signout-item" onClick={logout} disabled={busy}><LogOut size={17}/>{busy?'Signing out…':'Log out'}</button><div className="privacy-card"><ShieldCheck size={15}/><span><b>Your data stays yours</b><small>Private to your account</small></span></div></div></aside><main className="main-area"><header className="topbar"><button className="icon-button mobile-menu" onClick={()=>setDrawer(true)} aria-label="Open navigation"><Menu size={19}/></button><div className="crumb">My FitTrack <span>/</span><b>{title}</b></div><div className="top-actions"><span className="top-date"><CalendarDays size={15}/>{new Intl.DateTimeFormat('en',{weekday:'short',month:'short',day:'numeric'}).format(new Date())}</span><div className="profile-avatar small" title={account.full_name}>{account.full_name?.slice(0,1).toUpperCase()}</div></div></header><Routes><Route index element={<Dashboard/>}/><Route path="profile" element={<MyProfile notify={notify}/>}/><Route path="health" element={<HealthMetrics/>}/><Route path="goals" element={<GoalsWeight notify={notify}/>}/><Route path="activity" element={<ActivityTracking notify={notify}/>}/><Route path="history" element={<MyHistory/>}/><Route path="settings" element={<SettingsPage notify={notify}/>}/><Route path="*" element={<Navigate to="/app" replace/>}/></Routes></main></div> }

function PageTitle({eyebrow,title,copy,action}) { return <motion.div className="page-heading" {...enter}><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{copy}</p></div>{action}</motion.div> }
function MetricCard({icon:Icon,label,value,unit='',note='',tone=''}) { return <motion.article className="stat-card" {...enter}><div className="stat-top"><span className={`stat-icon ${tone}`}><Icon size={17}/></span><span className="stat-kicker">{label}</span></div><div className="stat-value">{value}<small>{unit}</small></div><div className="stat-foot">{note}</div></motion.article> }
function Empty({icon:Icon=Activity,title,copy,action}) { return <div className="empty-state"><span><Icon size={20}/></span><b>{title}</b><p>{copy}</p>{action}</div> }
function StepRing({ steps, goal, percentage }) {
  const radius = 43
  const circumference = 2 * Math.PI * radius
  const progress = goal == null || percentage == null ? 0 : Math.min(100, Math.max(0, Number(percentage)))
  return <div className="step-ring-wrap" role={goal == null ? undefined : 'progressbar'} aria-label={goal == null ? "Today's recorded steps" : "Today's step goal"} aria-valuenow={goal == null ? undefined : progress} aria-valuemin={goal == null ? undefined : 0} aria-valuemax={goal == null ? undefined : 100}>
    <svg className="step-ring" viewBox="0 0 112 112" aria-hidden="true"><circle className="step-ring-track" cx="56" cy="56" r={radius}/><circle className="step-ring-progress" cx="56" cy="56" r={radius} strokeDasharray={circumference} strokeDashoffset={circumference * (1 - progress / 100)}/></svg>
    <div className="step-ring-value"><b>{steps == null ? '—' : steps.toLocaleString()}</b><span>steps</span></div>
  </div>
}
function DashboardSectionMessage({ loading, error, onRetry, children }) {
  if (!loading && !error) return null
  return <div className={`dashboard-section-message ${error ? 'has-error' : ''}`} role={error ? 'alert' : 'status'}>
    {loading ? <><span className="spinner" />{children || 'Loading this section…'}</> : <><span>{error}</span><button className="text-link" onClick={onRetry}>Retry this section</button></>}
  </div>
}

function Dashboard() {
  const [summaryState, setSummaryState] = useState({ data: null, loading: true, error: '' })
  const [activityState, setActivityState] = useState({ data: null, loading: true, error: '' })
  const [fitnessState, setFitnessState] = useState({ data: null, loading: true, error: '' })
  const [goalState, setGoalState] = useState({ data: null, loading: true, error: '' })
  const [period, setPeriod] = useState('week')
  const [metric, setMetric] = useState('steps')
  const requestIds = useRef({ summary: 0, activity: 0, fitness: 0, goal: 0 })
  const { account } = useAuth()

  const requestSection = useCallback(async (key, request, validate, unavailableMessage, setState) => {
    const requestId = ++requestIds.current[key]
    setState({ data: null, loading: true, error: '' })
    const result = await loadDashboardSection(request, validate, unavailableMessage)
    if (requestIds.current[key] === requestId) setState(result)
  }, [])

  const loadSummary = useCallback(() => requestSection(
    'summary', getSummary, isRecord, 'Health and activity summary is unavailable.', setSummaryState,
  ), [requestSection])
  const loadActivity = useCallback(() => requestSection(
    'activity', () => getActivity(period), isRecordArray, 'Activity trend response was unavailable.', setActivityState,
  ), [period, requestSection])
  const loadFitness = useCallback(() => requestSection(
    'fitness', getFitness, isRecordArray, 'Recent activity response was unavailable.', setFitnessState,
  ), [requestSection])
  const loadGoal = useCallback(() => requestSection(
    'goal', getGoal, isRecord, 'Weight progress response was unavailable.', setGoalState,
  ), [requestSection])

  useEffect(() => { loadSummary(); loadFitness(); loadGoal() }, [loadSummary, loadFitness, loadGoal])
  useEffect(() => { loadActivity() }, [loadActivity])

  const summary = summaryState.data
  const goalData = goalState.data
  const recent = fitnessState.data || []
  const rows = activityState.data || []
  const chart = rows.filter(row => isIsoDate(row.record_date)).map(row => ({
    ...row,
    steps: row.steps == null || row.steps === '' || !Number.isFinite(Number(row.steps)) ? null : Number(row.steps),
    distance: row.distance == null || row.distance === '' || !Number.isFinite(Number(row.distance)) ? null : Number(row.distance),
    workout_minutes: row.workout_minutes == null || row.workout_minutes === '' || !Number.isFinite(Number(row.workout_minutes)) ? null : Number(row.workout_minutes),
    calories_burned: row.calories_burned == null || row.calories_burned === '' || !Number.isFinite(Number(row.calories_burned)) ? null : Number(row.calories_burned),
    day: new Date(`${row.record_date}T12:00:00`).toLocaleDateString('en', { weekday: 'short' }),
  }))
  const measures = {
    steps: ['Steps', '#34D399'],
    distance: ['Distance', '#34D399'],
    workout_minutes: ['Workout time', '#34D399'],
    calories_burned: ['Calories burned', '#34D399'],
  }
  const [metricLabel, metricColor] = measures[metric]
  const goal = goalData?.goal
  const progress = goalData?.progress
  const todaySteps = summary?.steps_today == null || !Number.isFinite(Number(summary.steps_today)) ? null : Number(summary.steps_today)
  const stepGoal = summary?.daily_step_goal
  const stepPercent = summary?.step_goal_percentage == null || !Number.isFinite(Number(summary.step_goal_percentage)) ? null : Number(summary.step_goal_percentage)
  const currentWeight = goalData?.current_weight_kg
  const weightHistoryCount = Number.isFinite(Number(progress?.history_count)) ? Number(progress.history_count) : 0
  const weeklyWeightChange = progress?.weekly_weight_change_kg
  const recentWorkouts = recent.filter(row => row.record_type === 'workout').slice(0, 3)
  const firstName = account?.full_name?.trim().split(/\s+/)[0] || 'there'
  const activityNote = summary?.activity_level_label
    ? `${summary.activity_level_label} · ×${finiteDisplay(summary?.activity_multiplier, 2)}`
    : 'Activity level not available'

  return <div className="page-wrap dashboard-page">
    <PageTitle eyebrow="YOUR HEALTH AT A GLANCE" title={`Good to see you, ${firstName}.`} copy="Your health baseline and recorded activity, together in one view." action={<Link to="/app/activity" className="button button-primary"><Plus size={16}/> Log activity</Link>}/>
    {summaryState.error && <DashboardSectionMessage error={summaryState.error} onRetry={loadSummary}/>}

    <section className="dashboard-section health-section">
      <div className="dashboard-section-heading"><div><span className="muted-label">HEALTH BASELINE</span><h2>Your key metrics</h2></div><Link to="/app/health" className="text-link">How they work <ArrowUpRight size={14}/></Link></div>
      <div className="stats-grid health-metric-grid">
        <MetricCard icon={Gauge} label="BODY MASS INDEX" value={summaryState.loading ? '—' : finiteDisplay(summary?.bmi, 1)} note={summaryState.loading ? 'Loading…' : summary?.bmi_category || (summaryState.error ? 'Unavailable' : 'Screening measure')} tone="lime"/>
        <MetricCard icon={HeartPulse} label="BASAL METABOLIC RATE" value={summaryState.loading ? '—' : finiteDisplay(summary?.bmr)} unit=" kcal/day" note={summaryState.loading ? 'Loading…' : 'Estimated energy at rest'} tone="violet"/>
        <MetricCard icon={Sparkles} label="DAILY MAINTENANCE" value={summaryState.loading ? '—' : finiteDisplay(summary?.tdee)} unit=" kcal/day" note={summaryState.loading ? 'Loading…' : activityNote} tone="orange"/>
        {summary?.daily_calorie_target != null && <MetricCard icon={Flame} label="GOAL CALORIE TARGET" value={finiteDisplay(summary.daily_calorie_target)} unit=" kcal/day" note="Configured with your fitness goal" tone="lime"/>}
      </div>
    </section>

    <section className="dashboard-progress-grid">
      <article className="panel weight-focus-panel">
        <div className="panel-heading"><div><span className="muted-label">WEIGHT PROGRESS</span><h2>{goal?.goal_label || 'Your weight'}</h2></div><Link to="/app/goals" className="text-link">Manage weight <ArrowUpRight size={14}/></Link></div>
        {goalState.loading || goalState.error
          ? <DashboardSectionMessage loading={goalState.loading} error={goalState.error} onRetry={loadGoal}>Loading weight progress…</DashboardSectionMessage>
          : <>
            <div className="weight-focus-content">
              <div className="weight-current"><span>{goal ? 'CURRENT WEIGHT' : 'PROFILE WEIGHT'}</span><div><b>{finiteDisplay(currentWeight, 1)}</b><i>kg</i></div><small>{goal ? 'Current profile value' : 'Profile value · not a dated weigh-in'}</small></div>
              {goal ? <div className="weight-target">
                <div className="weight-target-top"><div><span>TARGET</span><b>{finiteDisplay(progress?.target_weight_kg, 1)} <i>kg</i></b></div><span className="weight-goal-tag"><Target size={13}/>{goal.goal_label}</span></div>
                {progress?.progress_percentage == null ? <><div className="weight-maintenance-line"><span>MAINTENANCE PLAN</span><b>{progress?.maintenance_status?.replace('_',' ') || 'active'}</b></div><p>Change from start: {progress?.weight_change_kg == null ? 'Not enough weigh-ins' : `${Number(progress.weight_change_kg) > 0 ? '+' : ''}${finiteDisplay(progress.weight_change_kg, 1)} kg`}</p></> : <><div className="goal-progress-track" role="progressbar" aria-label="Weight goal progress" aria-valuenow={Math.round(Number(progress.progress_percentage) || 0)} aria-valuemin="0" aria-valuemax="100"><span style={{width:`${Math.min(100,Math.max(0,Number(progress.progress_percentage) || 0))}%`}}/></div><div className="weight-target-meta"><b>{finiteDisplay(progress.progress_percentage)}% complete</b><span>{finiteDisplay(progress.remaining_to_target_kg, 1)} kg remaining</span></div></>}
              </div> : <div className="weight-target weight-history-summary"><div><span>WEIGH-IN HISTORY</span><b>{weightHistoryCount ? `${weightHistoryCount} recorded` : 'No dated weigh-ins yet'}</b></div><p>{weeklyWeightChange == null ? 'Log measurements over time to see a real weekly trend.' : `Weekly change ${Number(weeklyWeightChange) > 0 ? '+' : ''}${finiteDisplay(weeklyWeightChange, 1)} kg, from recorded weigh-ins.`}</p></div>}
            </div>
            <div className="weight-focus-footer"><span><Activity size={14}/>{weeklyWeightChange == null ? 'Trend appears after dated measurements' : `Weekly change ${Number(weeklyWeightChange) > 0 ? '+' : ''}${finiteDisplay(weeklyWeightChange, 1)} kg`}</span><Link to="/app/goals">View weight history <ArrowRight size={14}/></Link></div>
          </>}
      </article>

      <article className="panel today-activity-spotlight">
        <div className="panel-heading"><div><span className="muted-label">TODAY</span><h2>Daily steps</h2></div><span className="stat-icon lime"><Footprints size={17}/></span></div>
        <div className="step-focus-content"><StepRing steps={summaryState.loading || summaryState.error ? null : todaySteps} goal={summaryState.loading || summaryState.error ? null : stepGoal} percentage={summaryState.loading || summaryState.error ? null : stepPercent}/><div className="step-focus-copy">
          <span>DAILY STEP GOAL</span>
          {summaryState.loading ? <><b>Loading step summary…</b><p>Your recorded progress will appear here.</p></> : summaryState.error ? <><b>Step summary unavailable</b><p>Retry the health and activity summary above.</p></> : stepGoal == null ? <><b>Make a target your own</b><p>Set a daily goal to see your step progress here.</p></> : <><b>{finiteDisplay(stepGoal)} steps</b><p>{stepPercent == null ? 'Progress unavailable' : `${finiteDisplay(stepPercent)}% of your goal`}{summary?.steps_remaining == null ? '' : ` · ${finiteDisplay(summary.steps_remaining)} remaining`}</p></>}
          <Link to="/app/activity" className="text-link">Activity tracking <ArrowUpRight size={14}/></Link>
        </div></div>
      </article>
    </section>

    <section className="dashboard-section all-time-section">
      <div className="dashboard-section-heading"><div><span className="muted-label">ALL-TIME TOTALS</span><h2>Recorded activity</h2></div><span className="dashboard-period-note">Across all recorded dates</span></div>
      <div className="stats-grid all-time-grid">
        <MetricCard icon={Footprints} label="TOTAL STEPS" value={summaryState.loading || summaryState.error ? '—' : finiteDisplay(summary?.steps)} note="All recorded days" tone="blue"/>
        <MetricCard icon={Activity} label="TOTAL DISTANCE" value={summaryState.loading || summaryState.error ? '—' : finiteDisplay(summary?.distance, 1)} unit=" km" note="All recorded cardio" tone="orange"/>
        <MetricCard icon={Timer} label="TOTAL EXERCISE TIME" value={summaryState.loading || summaryState.error ? '—' : finiteDisplay(summary?.workout_minutes)} unit=" min" note="All recorded activity" tone="pink"/>
        <MetricCard icon={Flame} label="EXERCISE CALORIES" value={summaryState.loading || summaryState.error ? '—' : finiteDisplay(summary?.calories_burned)} unit=" kcal" note="Manually recorded only" tone="lime"/>
      </div>
    </section>

    <section className="dashboard-grid dashboard-trends-grid">
      <motion.section className="panel chart-panel" {...enter}>
        <div className="panel-heading"><div><span className="muted-label">RECORDED TREND</span><h2>Activity over time</h2></div><span className="dashboard-period-note">{period === 'week' ? 'Last 7 days' : 'Last 30 days'}</span></div>
        <div className="chart-controls"><div className="chart-tabs">{Object.entries(measures).map(([key,[label]])=><button key={key} onClick={()=>setMetric(key)} className={metric===key?'selected':''}>{label}</button>)}</div><div className="chart-tabs">{[['week','7 days'],['month','30 days']].map(([value,label])=><button key={value} onClick={()=>setPeriod(value)} className={value===period?'selected':''}>{label}</button>)}</div></div>
        <div className="dashboard-chart-slot">{activityState.loading
          ? <DashboardSectionMessage loading>Loading activity trend…</DashboardSectionMessage>
          : activityState.error
            ? <DashboardSectionMessage error={activityState.error} onRetry={loadActivity}/>
            : chart.length ? <div className="chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={chart} margin={{left:0,right:12,top:12,bottom:0}}><defs><linearGradient id="personalSteps" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={metricColor} stopOpacity={.26}/><stop offset="100%" stopColor={metricColor} stopOpacity={0}/></linearGradient></defs><CartesianGrid stroke="#263442" strokeDasharray="3 5" vertical={false}/><XAxis dataKey="day" axisLine={false} tickLine={false} tickMargin={8} tick={{fill:'#AAB6C4',fontSize:11}}/><YAxis width={42} axisLine={false} tickLine={false} tickMargin={6} tick={{fill:'#94A3B8',fontSize:10}}/><Tooltip cursor={{stroke:'#64748B',strokeDasharray:'4 4'}} contentStyle={{background:'#151D26',border:'1px solid #344354',borderRadius:10,color:'#F8FAFC',fontSize:12}} formatter={value=>[finiteDisplay(value),metricLabel]}/><Area dataKey={metric} type="monotone" stroke={metricColor} strokeWidth={2.8} activeDot={{r:4,stroke:'#0B0F14',strokeWidth:2}} dot={false} fill="url(#personalSteps)"/></AreaChart></ResponsiveContainer></div> : <Empty icon={Footprints} title="No activity in this period" copy="Log an activity to see your real daily trend." action={<Link className="text-link" to="/app/activity">Log activity <ArrowRight size={14}/></Link>}/>}</div>
      </motion.section>
      <div className="dashboard-side-stack">
        <section className="panel recent-activity-panel"><div className="panel-heading"><div><span className="muted-label">LATEST RECORDS</span><h2>Recent activity</h2></div><Link to="/app/history" className="text-link">History <ArrowUpRight size={14}/></Link></div>{fitnessState.loading
          ? <DashboardSectionMessage loading>Loading recent activity…</DashboardSectionMessage>
          : fitnessState.error
            ? <DashboardSectionMessage error={fitnessState.error} onRetry={loadFitness}/>
            : recent.length ? <div className="dashboard-recent-list">{recent.slice(0,4).map((row,index)=><article key={row.record_id ?? `${row.record_date || 'record'}-${index}`}><span className="dashboard-recent-icon">{row.record_type==='workout'?<Dumbbell size={15}/>:row.record_type==='cardio'?<Bike size={15}/>:<Footprints size={15}/>}</span><div><b>{row.record_type==='workout'?row.workout_name||'Workout':row.record_type==='cardio'?`${row.activity_type||'Cardio'} session`:'Daily steps'}</b><small>{isIsoDate(row.record_date) ? new Date(`${row.record_date}T12:00:00`).toLocaleDateString('en',{month:'short',day:'numeric'}) : 'Date unavailable'} · {row.record_type==='daily'?`${finiteDisplay(row.steps)} steps`:row.workout_minutes==null?'Duration not recorded':`${finiteDisplay(row.workout_minutes)} min`}</small></div></article>)}</div> : <Empty icon={Activity} title="No recent activity" copy="No recent records yet." action={<Link className="text-link" to="/app/history">View history <ArrowRight size={14}/></Link>}/>}</section>
        <section className="panel recent-workouts-panel dashboard-workouts"><div className="panel-heading"><div><span className="muted-label">RECENT SESSIONS</span><h2>Recent workouts</h2></div><Link to="/app/activity" className="text-link">Log a workout <ArrowUpRight size={14}/></Link></div>{fitnessState.loading
          ? <DashboardSectionMessage loading>Loading recent workouts…</DashboardSectionMessage>
          : fitnessState.error
            ? <DashboardSectionMessage error={fitnessState.error} onRetry={loadFitness}/>
            : recentWorkouts.length?<div className="dashboard-workout-list">{recentWorkouts.map((row,index)=><article key={row.record_id ?? `workout-${index}`}><span className="dashboard-recent-icon"><Dumbbell size={15}/></span><div><b>{row.workout_name||'Workout'}</b><small>{row.workout_category?.replaceAll('_',' ')||'Workout'} · {row.workout_minutes == null ? '—' : finiteDisplay(row.workout_minutes)} min · {isIsoDate(row.record_date) ? row.record_date : 'Date unavailable'}</small></div></article>)}</div>:<Empty icon={Dumbbell} title="No workouts recorded" copy="No recorded sessions yet." action={<Link className="text-link" to="/app/activity">Open workouts <ArrowRight size={14}/></Link>}/>}</section>
      </div>
    </section>
  </div>
}

function Records({rows}) { return rows.length?<div className="table-scroll"><table><thead><tr><th>DATE</th><th>ACTIVITY</th><th>STEPS</th><th>DURATION</th><th>DISTANCE</th><th>CALORIES</th></tr></thead><tbody>{rows.map(r=><tr key={r.record_id}><td>{new Date(`${r.record_date}T12:00:00`).toLocaleDateString('en',{month:'short',day:'numeric',year:'numeric'})}</td><td>{r.record_type==='workout'?r.workout_name||'Workout':r.record_type==='cardio'?r.activity_type:'Daily steps'}</td><td>{r.steps==null?'—':Number(r.steps).toLocaleString()}</td><td>{r.workout_minutes==null?'—':`${r.workout_minutes} min`}</td><td>{r.distance==null?'—':`${Number(r.distance).toFixed(1)} km`}</td><td>{r.calories_burned==null?'—':`${Math.round(r.calories_burned)} kcal`}</td></tr>)}</tbody></table></div>:<Empty icon={Footprints} title="No activity recorded yet" copy="When you log your first activity, it will appear here."/> }

const blankProfile={full_name:'',age:'',gender:'female',height:'',weight:'',activity_level:'moderate'}
function ProfileEditor({ onboarding = false, notify = () => {}, onSaved = () => {} }) {
  const { account } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ ...blankProfile, full_name: account?.full_name || '' })
  const [loading, setLoading] = useState(!onboarding)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const submissionLock = useRef(false)

  useEffect(() => {
    if (!onboarding) {
      getProfile()
        .then(response => {
          const profile = response.data.profile
          if (profile) {
            setForm({
              ...blankProfile,
              ...profile,
              full_name: profile.name ?? account?.full_name ?? '',
              age: String(profile.age ?? ''),
              height: String(profile.height ?? ''),
              weight: String(profile.weight ?? ''),
            })
          }
        })
        .catch(requestError => setError(requestError.message))
        .finally(() => setLoading(false))
    }
  }, [account?.full_name, onboarding])

  const change = event => {
    const { name, value } = event.target
    setForm(current => ({ ...current, [name]: value }))
    if (name === 'age' || name === 'weight') setError('')
  }

  const submit = async event => {
    event.preventDefault()
    if (!beginSubmission(submissionLock)) return
    setError('')

    const ageText = form.age.trim()
    if (!/^\d+$/.test(ageText) || Number(ageText) < 1 || Number(ageText) > 120) {
      setError('Age must be a whole number between 1 and 120.')
      finishSubmission(submissionLock)
      return
    }
    const weightText = form.weight.trim()
    const weightValue = Number(weightText)
    if (!weightText || !Number.isFinite(weightValue) || weightValue < 1 || weightValue > 500) {
      setError('Weight must be a number from 1 to 500 kg.')
      finishSubmission(submissionLock)
      return
    }
    if (!event.currentTarget.checkValidity()) {
      event.currentTarget.reportValidity()
      finishSubmission(submissionLock)
      return
    }

    setBusy(true)
    try {
      await saveProfile({
        ...form,
        age: Number(ageText),
        height: Number(form.height),
        weight: weightValue,
      })
      await onSaved()
      notify(onboarding ? 'Your personal profile is ready.' : 'Profile updated')
      navigate('/app')
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      finishSubmission(submissionLock)
      setBusy(false)
    }
  }

  return (
    <div className="page-wrap">
      {onboarding
        ? <PageTitle eyebrow="LET’S SET YOUR BASELINE" title="Make FitTrack yours." copy="Add your health details to calculate your personal estimates." />
        : <PageTitle eyebrow="YOUR INFORMATION" title="My Profile" copy="Keep your health information current for relevant estimates." />}
      {loading
        ? <div className="loading-panel"><span className="spinner" /> Loading your profile…</div>
        : (
          <motion.section className="panel editor-panel" {...enter}>
            <form className="form-stack personal-form" onSubmit={submit}>
              <div className="form-section-title">
                <span className="stat-icon lime"><CircleUserRound size={17} /></span>
                <div><b>Personal details</b><small>Only you can see this information.</small></div>
              </div>
              <label>Full name
                <input name="full_name" value={form.full_name} onChange={change} maxLength="100" autoComplete="name" required />
              </label>
              <div className="form-row">
                <label>Age
                  <input name="age" type="number" min="1" max="120" step="1" value={form.age} onChange={change} required />
                </label>
                <label>Gender
                  <select name="gender" value={form.gender} onChange={change}>
                    <option value="female">Female</option><option value="male">Male</option>
                  </select>
                </label>
              </div>
              <div className="form-row">
                <label>Height <i>meters</i>
                  <input name="height" type="number" step="0.01" min="0.01" max="3" value={form.height} onChange={change} placeholder="1.70" required />
                </label>
                <label>Weight <i>kg</i>
                  <input name="weight" type="text" inputMode="decimal" value={form.weight} onChange={change} placeholder="65" required />
                </label>
              </div>
              <label>Typical activity level
                <select name="activity_level" value={form.activity_level} onChange={change}>
                  <option value="sedentary">Mostly sitting</option>
                  <option value="light">Lightly active</option>
                  <option value="moderate">Moderately active</option>
                  <option value="active">Very active</option>
                  <option value="very_active">Extremely active</option>
                </select>
                <small className="field-note">Saved to your profile. Daily calorie estimates continue using FitTrack’s original ×1.2 assumption.</small>
              </label>
              {error && <div className="form-error" role="alert">{error}</div>}
              <div className="calc-disclaimer"><HeartPulse size={15} />BMI and calorie values are estimates for general tracking. They do not diagnose health conditions.</div>
              <button className="button button-primary form-submit" disabled={busy}>
                {busy ? 'Saving…' : onboarding ? 'Complete my profile' : 'Save profile'}<ArrowRight size={15} />
              </button>
            </form>
          </motion.section>
        )}
    </div>
  )
}
function MyProfile({notify}) { const {refresh}=useAuth();return <ProfileEditor notify={notify} onSaved={refresh}/> }
function HealthMetrics() {
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const load = useCallback(() => {
    setLoading(true)
    getProfile()
      .then(response => { setProfile(response.data.profile); setError('') })
      .catch(requestError => setError(requestError.message))
      .finally(() => setLoading(false))
  }, [])
  useEffect(() => { load() }, [load])

  const activityNote = profile
    ? `${profile.activity_level_label} (×${profile.activity_multiplier})`
    : ''
  const targetValue = profile?.daily_calorie_target == null
    ? 'Not set'
    : Math.round(profile.daily_calorie_target).toLocaleString()

  return (
    <div className="page-wrap">
      <PageTitle eyebrow="YOUR PERSONAL BASELINE" title="Health Metrics" copy="Understand the estimates calculated from your profile."
        action={<Link to="/app/profile" className="button button-ghost">Update profile <ArrowUpRight size={14} /></Link>} />
      {error && <div className="form-error" role="alert">{error} <button className="text-link" onClick={load}>Try again</button></div>}
      {loading
        ? <div className="loading-panel"><span className="spinner" /> Loading your metrics…</div>
        : !error && !profile
          ? <Empty icon={Gauge} title="Profile metrics are unavailable" copy="Complete or update your profile to see health estimates." />
        : profile && (
          <>
            <div className="stats-grid health-grid">
              <MetricCard icon={Gauge} label="BODY MASS INDEX" value={Number(profile.bmi).toFixed(2)}
                note={`${profile.bmi_category} · Screening measure`} tone="lime" />
              <MetricCard icon={HeartPulse} label="BASAL METABOLIC RATE" value={Math.round(profile.bmr).toLocaleString()}
                unit=" kcal/day" note="Estimated energy at rest" tone="violet" />
              <MetricCard icon={Sparkles} label="TDEE / MAINTENANCE" value={Math.round(profile.tdee).toLocaleString()}
                unit=" kcal/day" note={activityNote} tone="orange" />
              <MetricCard icon={Gauge} label="GOAL CALORIE TARGET" value={targetValue}
                unit={profile.daily_calorie_target == null ? '' : ' kcal/day'}
                note={profile.daily_calorie_target == null ? 'No target is configured; this is not inferred from TDEE.' : 'Suggested by your fitness goal'} tone="violet" />
            </div>
            <section className="panel metrics-explainer">
              <div className="panel-heading"><div><span className="muted-label">ABOUT THESE ESTIMATES</span><h2>How your numbers are calculated</h2></div></div>
              <div className="metric-formulas">
                <article><b>BMI · {profile.bmi_category}</b><code>weight ÷ height²</code><p>{profile.bmi_explanation}</p></article>
                <article><b>BMR</b><code>Mifflin–St Jeor</code><p>{profile.bmr_explanation} Height is converted from meters to centimeters.</p></article>
                <article><b>TDEE · maintenance</b><code>BMR × {profile.activity_multiplier}</code><p>{profile.tdee_explanation} Your profile activity level is {profile.activity_level_label.toLowerCase()}.</p></article>
              </div>
              <p className="form-hint">Goal calorie suggestions appear after you set a fitness goal. Exercise calories are tracked separately. These estimates do not diagnose health conditions.</p>
            </section>
          </>
        )}
    </div>
  )
}
function GoalsWeight({ notify }) {
  const [profile, setProfile] = useState(null)
  const [goalData, setGoalData] = useState(null)
  const [records, setRecords] = useState([])
  const [goalForm, setGoalForm] = useState({
    goal_type: 'weight_loss', target_weight_kg: '', calorie_adjustment: '300', confirm_calorie_target: false,
  })
  const [weightForm, setWeightForm] = useState({ weight_kg: '', recorded_at: today() })
  const [editing, setEditing] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const submissionLock = useRef(false)
  const goalFormInitialized = useRef(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [profileResponse, goalResponse, weightResponse] = await Promise.all([
        getProfile(), getGoal(), getWeightHistory(),
      ])
      const nextProfile = profileResponse.data.profile
      const nextGoalData = goalResponse.data
      setProfile(nextProfile)
      setGoalData(nextGoalData)
      setRecords(weightResponse.data.records)
      // StrictMode can start this initial load twice. Initialize the editable
      // form once so a slower duplicate response cannot overwrite user edits.
      if (!goalFormInitialized.current) {
        goalFormInitialized.current = true
        setGoalForm(current => ({
          ...current,
          goal_type: nextGoalData.goal?.goal_type || current.goal_type,
          target_weight_kg: nextGoalData.goal
            ? String(nextGoalData.goal.target_weight_kg)
            : String(nextGoalData.current_weight_kg ?? nextProfile?.weight ?? ''),
          calorie_adjustment: nextGoalData.goal
            ? String(nextGoalData.goal.calorie_adjustment)
            : current.calorie_adjustment,
          confirm_calorie_target: Boolean(nextGoalData.goal?.daily_calorie_target),
        }))
      }
      setError('')
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const goal = goalData?.goal
  const progress = goalData?.progress
  const currentWeight = goalData?.current_weight_kg ?? profile?.weight
  const adjustment = Number(goalForm.calorie_adjustment)
  const suggestedCalories = profile?.tdee == null
    ? null
    : goalForm.goal_type === 'maintenance'
      ? Number(profile.tdee)
      : Number.isFinite(adjustment)
        ? Number(profile.tdee) + (goalForm.goal_type === 'weight_loss' ? -adjustment : adjustment)
        : null
  const formatWeight = value => value == null ? '—' : Number(value).toFixed(1)
  const formatChange = value => value == null
    ? 'Not enough history'
    : `${Number(value) > 0 ? '+' : ''}${Number(value).toFixed(1)} kg`
  const chartRows = records.slice().reverse().map(record => ({
    ...record,
    day: String(record.recorded_at).slice(5, 10),
  }))

  const changeGoalType = event => {
    const goalType = event.target.value
    setGoalForm(current => ({
      ...current,
      goal_type: goalType,
      target_weight_kg: goalType === 'maintenance' ? String(currentWeight ?? '') : current.target_weight_kg,
      calorie_adjustment: goalType === 'weight_loss' ? '300' : goalType === 'maintenance' ? '0' : '200',
      confirm_calorie_target: false,
    }))
    setError('')
  }

  const submitGoal = async event => {
    event.preventDefault()
    if (!beginSubmission(submissionLock)) return
    setError('')
    if (goal && !window.confirm('Starting a new goal will reset its starting weight to your current weight. Continue?')) {
      finishSubmission(submissionLock)
      return
    }
    setBusy(true)
    try {
      const response = await saveGoal({
        goal_type: goalForm.goal_type,
        target_weight_kg: goalForm.target_weight_kg === '' ? null : Number(goalForm.target_weight_kg),
        calorie_adjustment: Number(goalForm.calorie_adjustment),
        confirm_calorie_target: goalForm.confirm_calorie_target,
      })
      setGoalData(response.data)
      const savedGoal = response.data.goal
      if (savedGoal) {
        goalFormInitialized.current = true
        setGoalForm({
          goal_type: savedGoal.goal_type,
          target_weight_kg: String(savedGoal.target_weight_kg),
          calorie_adjustment: String(savedGoal.calorie_adjustment),
          confirm_calorie_target: savedGoal.daily_calorie_target != null,
        })
      }
      notify(goal ? 'Your fitness goal was restarted.' : 'Your fitness goal was saved.')
      await load()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      finishSubmission(submissionLock)
      setBusy(false)
    }
  }

  const saveWeight = async event => {
    event.preventDefault()
    if (!beginSubmission(submissionLock)) return
    setError('')
    setBusy(true)
    try {
      await addWeight({ weight_kg: Number(weightForm.weight_kg), recorded_at: weightForm.recorded_at })
      setWeightForm({ weight_kg: '', recorded_at: today() })
      notify('Weight entry saved')
      await load()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      finishSubmission(submissionLock)
      setBusy(false)
    }
  }

  const saveCorrection = async event => {
    event.preventDefault()
    if (!beginSubmission(submissionLock)) return
    setError('')
    setBusy(true)
    try {
      await updateWeight(editing.record_id, {
        weight_kg: Number(editing.weight_kg),
        recorded_at: editing.recorded_at,
      })
      setEditing(null)
      notify('Weight entry corrected')
      await load()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      finishSubmission(submissionLock)
      setBusy(false)
    }
  }

  const removeWeight = async recordId => {
    if (!window.confirm('Delete this weight entry? This cannot be undone.')) return
    if (!beginSubmission(submissionLock)) return
    setError('')
    setBusy(true)
    try {
      await deleteWeight(recordId)
      notify('Weight entry deleted')
      await load()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      finishSubmission(submissionLock)
      setBusy(false)
    }
  }

  const changeStatus = async status => {
    if (status === 'cancelled' && !window.confirm('Cancel this fitness goal?')) return
    if (!beginSubmission(submissionLock)) return
    setError('')
    setBusy(true)
    try {
      const response = await setGoalStatus(status)
      setGoalData(response.data)
      notify(status === 'paused' ? 'Goal paused' : status === 'active' ? 'Goal resumed' : 'Goal cancelled')
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      finishSubmission(submissionLock)
      setBusy(false)
    }
  }

  if (loading && !profile) {
    return <div className="page-wrap"><div className="loading-panel"><span className="spinner" /> Loading your goal and weight history…</div></div>
  }

  return (
    <div className="page-wrap">
      <PageTitle eyebrow="YOUR PERSONAL PLAN" title="Goals & Weight" copy="Set a goal, review its calorie assumptions, and track real weigh-ins." />
      {error && <div className="form-error page-error" role="alert">{error}</div>}
      {!profile
        ? error
          ? <section className="panel"><p>Unable to load your profile, goals and weight history.</p><button className="button button-primary" onClick={load}>Try again</button></section>
          : <Empty icon={Target} title="Complete your profile first" copy="Your profile provides the health and maintenance estimates used for goal setup." action={<Link to="/app/profile" className="button button-ghost">Review profile</Link>} />
        : (
          <>
            <div className="goals-layout">
              <motion.section className="panel editor-panel goal-editor" {...enter}>
                <div className="panel-heading">
                  <div><span className="muted-label">FITNESS GOAL</span><h2>{goal ? 'Review your plan' : 'Choose your direction'}</h2></div>
                  <span className="stat-icon lime"><Target size={17} /></span>
                </div>
                <form className="form-stack personal-form" onSubmit={submitGoal}>
                  <label>Goal type
                    <select value={goalForm.goal_type} onChange={changeGoalType} disabled={busy}>
                      <option value="weight_loss">Weight loss</option>
                      <option value="maintenance">Maintenance</option>
                      <option value="weight_gain">Weight gain</option>
                      <option value="muscle_building">Muscle building</option>
                    </select>
                  </label>
                  <label>Target weight <i>kg</i>
                    <input type="number" min="1" max="500" step="0.1" value={goalForm.target_weight_kg}
                      onChange={event => {
                        const targetWeight = event.currentTarget.value
                        setGoalForm(current => ({ ...current, target_weight_kg: targetWeight }))
                      }} required={goalForm.goal_type !== 'maintenance'} readOnly={goalForm.goal_type === 'maintenance'} disabled={busy} />
                    <small className="field-note">{goalForm.goal_type === 'weight_loss' ? 'Choose a target below your current weight.' : ['weight_gain', 'muscle_building'].includes(goalForm.goal_type) ? 'Choose a target above your current weight.' : 'Maintenance uses your current weight.'} Starting weight is captured from your profile ({formatWeight(currentWeight)} kg) when saved.</small>
                  </label>
                  {goalForm.goal_type !== 'maintenance' && (
                    <label>Daily calorie adjustment <i>kcal</i>
                      <input type="number" min="100" max={goalForm.goal_type === 'weight_loss' ? '500' : '300'} step="25"
                        value={goalForm.calorie_adjustment}
                        onChange={event => {
                          const adjustment = event.currentTarget.value
                          setGoalForm(current => ({ ...current, calorie_adjustment: adjustment, confirm_calorie_target: false }))
                        }} required disabled={busy} />
                      <small className="field-note">
                        {goalForm.goal_type === 'weight_loss'
                          ? 'Conservative estimated deficit: 100–500 kcal/day. Default suggestion: 300.'
                          : 'Modest estimated surplus: 100–300 kcal/day. Default suggestion: 200.'}
                      </small>
                    </label>
                  )}
                  <div className="goal-calorie-preview">
                    <span className="muted-label">ESTIMATED DAILY INTAKE</span>
                    <strong>{suggestedCalories == null ? '—' : Math.round(suggestedCalories).toLocaleString()} <small>kcal/day</small></strong>
                    <p>{goalForm.goal_type === 'maintenance'
                      ? 'Maintenance estimate equals your current TDEE.'
                      : `TDEE ${goalForm.goal_type === 'weight_loss' ? 'minus' : 'plus'} ${Number.isFinite(adjustment) ? adjustment : '—'} kcal/day for this ${goalForm.goal_type === 'muscle_building' ? 'muscle-building' : goalForm.goal_type === 'weight_gain' ? 'weight-gain' : 'weight-loss'} estimate.`}</p>
                  </div>
                  <label className="goal-confirm">
                    <input type="checkbox" checked={goalForm.confirm_calorie_target}
                      onChange={event => {
                        const confirmed = event.currentTarget.checked
                        setGoalForm(current => ({ ...current, confirm_calorie_target: confirmed }))
                      }} disabled={busy} />
                    I reviewed and confirm this estimated intake target.
                  </label>
                  <small className="field-note">This is an estimate, not a medical prescription. Muscle gain is not inferred from weight; FitTrack does not yet track strength sessions.</small>
                  <button className="button button-primary form-submit" disabled={busy}>{busy ? 'Saving…' : goal ? 'Update goal' : 'Save goal'}</button>
                </form>
                {goal && (
                  <div className="goal-status-controls">
                    <span className={`goal-status status-${goal.status}`}>{goal.status.replace('_', ' ')}</span>
                    {goal.status === 'active' && <button className="text-link" disabled={busy} onClick={() => changeStatus('paused')}>Pause</button>}
                    {goal.status === 'paused' && <button className="text-link" disabled={busy} onClick={() => changeStatus('active')}>Resume</button>}
                    {!['completed', 'cancelled'].includes(goal.status) && <button className="text-link goal-cancel" disabled={busy} onClick={() => changeStatus('cancelled')}>Cancel goal</button>}
                  </div>
                )}
              </motion.section>

              <motion.section className="panel editor-panel goal-editor" {...enter}>
                <div className="panel-heading">
                  <div><span className="muted-label">WEIGHT ENTRY</span><h2>Log a weigh-in</h2></div>
                  <span className="stat-icon lime"><Gauge size={17} /></span>
                </div>
                <form className="form-stack personal-form" onSubmit={saveWeight}>
                  <label>Weight <i>kg</i>
                    <input type="number" inputMode="decimal" min="1" max="500" step="0.01" value={weightForm.weight_kg}
                      onChange={event => setWeightForm(current => ({ ...current, weight_kg: event.target.value }))} placeholder="e.g. 72.5" required />
                  </label>
                  <label>Recorded date
                    <input type="date" value={weightForm.recorded_at}
                      onChange={event => setWeightForm(current => ({ ...current, recorded_at: event.target.value }))} required />
                  </label>
                  <small className="field-note">Only weigh-ins you enter appear in your history; existing profile weight is not backfilled.</small>
                  <button className="button button-primary form-submit" disabled={busy}>Save weight</button>
                </form>
              </motion.section>
            </div>

            {goal && progress && (
              <section className="stats-grid goal-progress-grid">
                <MetricCard icon={Gauge} label="STARTING WEIGHT" value={formatWeight(progress.starting_weight_kg)} unit=" kg" note={new Date(goal.created_at.replace(' ', 'T')).toLocaleDateString()} tone="violet" />
                <MetricCard icon={Activity} label="CURRENT WEIGHT" value={formatWeight(progress.current_weight_kg)} unit=" kg" note="Latest value in your profile" tone="lime" />
                <MetricCard icon={Target} label="TARGET WEIGHT" value={formatWeight(progress.target_weight_kg)} unit=" kg" note={goal.goal_label} tone="blue" />
                <MetricCard icon={Activity} label={goal.goal_type === 'maintenance' ? 'CHANGE FROM START' : goal.goal_type === 'weight_loss' ? 'TOTAL WEIGHT LOST' : 'TOTAL WEIGHT GAINED'}
                  value={formatWeight(goal.goal_type === 'maintenance' ? progress.weight_change_kg : goal.goal_type === 'weight_loss' ? progress.total_weight_lost_kg : progress.total_weight_gained_kg)} unit=" kg"
                  note="Change from the goal starting weight" tone="pink" />
                <MetricCard icon={Gauge} label={goal.goal_type === 'maintenance' ? 'DEVIATION FROM TARGET' : 'REMAINING TO TARGET'}
                  value={formatWeight(progress.remaining_to_target_kg)} unit=" kg"
                  note={goal.goal_type === 'maintenance' ? (progress.maintenance_status === 'stable' ? 'Within 0.5 kg of target' : progress.maintenance_status?.replace('_', ' ')) : `${formatWeight(progress.progress_percentage)}% complete`} tone="orange" />
                <MetricCard icon={Footprints} label="WEEKLY WEIGHT CHANGE" value={formatChange(progress.weekly_weight_change_kg)} note="Compared with a logged measurement 7–14 days before latest" tone="pink" />
                <MetricCard icon={CalendarDays} label="MONTHLY WEIGHT CHANGE" value={formatChange(progress.monthly_weight_change_kg)} note="Compared with a logged measurement 30–37 days before latest" tone="violet" />
              </section>
            )}
            {!goal && progress && (
              <section className="stats-grid goal-progress-grid">
                <MetricCard icon={Activity} label="CURRENT WEIGHT" value={formatWeight(currentWeight)} unit=" kg" note="From your personal profile" tone="lime" />
                <MetricCard icon={Footprints} label="WEEKLY WEIGHT CHANGE" value={formatChange(progress.weekly_weight_change_kg)} note="Requires real measurements 7–14 days apart" tone="pink" />
                <MetricCard icon={CalendarDays} label="MONTHLY WEIGHT CHANGE" value={formatChange(progress.monthly_weight_change_kg)} note="Requires real measurements 30–37 days apart" tone="violet" />
              </section>
            )}

            <section className="panel history-chart weight-history-chart">
              <div className="panel-heading"><div><span className="muted-label">YOUR MEASUREMENTS</span><h2>Weight history</h2></div><span className="muted-label">{records.length} ENTRIES</span></div>
              {chartRows.length
                ? <div className="chart"><ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartRows} margin={{ left: -16, right: 8, top: 10, bottom: 0 }}>
                    <defs><linearGradient id="weightHistoryFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#34D399" stopOpacity={.2} /><stop offset="100%" stopColor="#34D399" stopOpacity={0} /></linearGradient></defs>
                    <CartesianGrid stroke="#222a25" vertical={false} />
                    <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fill: '#79827b', fontSize: 10 }} />
                    <YAxis domain={['dataMin - 2', 'dataMax + 2']} axisLine={false} tickLine={false} tick={{ fill: '#79827b', fontSize: 10 }} />
                    <Tooltip contentStyle={{ background: '#171d19', border: '1px solid #2b352d', borderRadius: 10, color: '#eef2e9' }}
                      formatter={value => [`${Number(value).toFixed(2)} kg`, 'Weight']} />
                    <Area dataKey="weight_kg" type="monotone" stroke="#34D399" strokeWidth={2.5} fill="url(#weightHistoryFill)" />
                  </AreaChart>
                </ResponsiveContainer></div>
                : <Empty icon={Gauge} title="No weight history yet" copy="Log a weigh-in to start a real history. Your current profile weight is not treated as a dated measurement." />}
            </section>

            <section className="panel records-panel">
              <div className="panel-heading"><div><span className="muted-label">WEIGH-INS</span><h2>Recorded weights</h2></div></div>
              {records.length
                ? <div className="table-scroll"><table><thead><tr><th>RECORDED</th><th>WEIGHT</th><th>ACTIONS</th></tr></thead>
                  <tbody>{records.map(record => editing?.record_id === record.record_id
                    ? <tr key={record.record_id}><td><input type="date" value={editing.recorded_at} onChange={event => setEditing({ ...editing, recorded_at: event.target.value })} /></td>
                      <td><input type="number" min="1" max="500" step="0.01" value={editing.weight_kg} onChange={event => setEditing({ ...editing, weight_kg: event.target.value })} /></td>
                      <td><button className="text-link" disabled={busy} onClick={saveCorrection}>Save</button><button className="text-link" onClick={() => setEditing(null)}>Cancel</button></td></tr>
                    : <tr key={record.record_id}><td>{String(record.recorded_at).slice(0, 16)}</td><td>{Number(record.weight_kg).toFixed(2)} kg</td>
                      <td><button className="text-link" aria-label="Edit weight" onClick={() => setEditing({ record_id: record.record_id, weight_kg: String(record.weight_kg), recorded_at: String(record.recorded_at).slice(0, 10) })}><Pencil size={13} /></button>
                        <button className="text-link goal-delete" aria-label="Delete weight" disabled={busy} onClick={() => removeWeight(record.record_id)}><Trash2 size={13} /></button></td></tr>)}</tbody>
                  </table></div>
                : <Empty icon={HistoryIcon} title="No weigh-ins to show" copy="Entries appear here after you log a weight." />}
            </section>
          </>
        )}
    </div>
  )
}

function MyHistory() {
  const [rows, setRows] = useState([])
  const [range, setRange] = useState({ start: '', end: '' })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const load = useCallback(() => {
    setLoading(true)
    getFitness(range)
      .then(response => { setRows(response.data); setError('') })
      .catch(requestError => setError(requestError.message))
      .finally(() => setLoading(false))
  }, [range])
  useEffect(() => { load() }, [load])
  const chart = rows.slice().reverse().map(row => ({
    ...row,
    day: new Date(`${row.record_date}T12:00:00`).toLocaleDateString('en', { month: 'short', day: 'numeric' }),
  }))
  return (
    <div className="page-wrap">
      <PageTitle eyebrow="YOUR RECORD, OVER TIME" title="My History" copy="A private record of your daily movement and workouts."
        action={<Link to="/app/activity" className="button button-primary"><Plus size={15} /> Log activity</Link>} />
      <div className="filter-bar panel">
        <div className="filter-title"><CalendarDays size={16} /> Filter your history</div>
        <label>From<input type="date" value={range.start} onChange={event => setRange({ ...range, start: event.target.value })} /></label>
        <label>To<input type="date" value={range.end} onChange={event => setRange({ ...range, end: event.target.value })} /></label>
        <button className="text-link" onClick={() => setRange({ start: '', end: '' })}>Clear</button>
      </div>
      {error && <div className="form-error" role="alert">{error} <button className="text-link" onClick={load}>Try again</button></div>}
      <section className="panel history-chart">
        <div className="panel-heading"><div><span className="muted-label">PERSONAL TREND</span><h2>Steps per day</h2></div><span className="muted-label">{loading || error ? '—' : `${rows.length} ENTRIES`}</span></div>
        {loading
          ? <div className="loading-panel"><span className="spinner" /> Loading your activity trend…</div>
          : error
            ? <p className="dashboard-note">The trend is unavailable until your activity history loads.</p>
            : chart.length
              ? <div className="chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={chart} margin={{ left: -18, right: 8, top: 10, bottom: 0 }}><defs><linearGradient id="historyPersonal" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#34D399" stopOpacity={.2} /><stop offset="100%" stopColor="#34D399" stopOpacity={0} /></linearGradient></defs><CartesianGrid stroke="#222a25" vertical={false} /><XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fill: '#79827b', fontSize: 11 }} /><YAxis axisLine={false} tickLine={false} tick={{ fill: '#79827b', fontSize: 10 }} /><Tooltip contentStyle={{ background: '#171d19', border: '1px solid #2b352d', borderRadius: 10, color: '#eef2e9' }} formatter={value => [Number(value).toLocaleString(), 'Steps']} /><Area dataKey="steps" type="monotone" stroke="#34D399" strokeWidth={2.5} fill="url(#historyPersonal)" /></AreaChart></ResponsiveContainer></div>
              : <Empty icon={HistoryIcon} title="Nothing in this date range" copy="Your activity entries will appear here after you log them." />}
      </section>
      <section className="panel records-panel">
        <div className="panel-heading"><div><span className="muted-label">YOUR ACTIVITY</span><h2>History</h2></div></div>
        {loading ? <div className="loading-panel"><span className="spinner" /> Loading your history…</div> : error ? <p className="dashboard-note">Activity records are unavailable until the request succeeds.</p> : <Records rows={rows} />}
      </section>
    </div>
  )
}
function SettingsPage({notify}) {
  const [form,setForm]=useState({current_password:'',new_password:'',confirm_password:''})
  const [typed,setTyped]=useState(''),[deletePassword,setDeletePassword]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('')
  const {account,setAccount}=useAuth(),navigate=useNavigate()
  const hasPassword=Boolean(account?.has_password)
  const submit=async e=>{e.preventDefault();setError('');setBusy(true);try{await changePassword(form);setForm({current_password:'',new_password:'',confirm_password:''});notify('Password updated');await authApi.me().then(r=>setAccount(r.data.account))}catch(e){setError(e.message)}finally{setBusy(false)}}
  const remove=async()=>{if(typed!=='DELETE')return;setBusy(true);setError('');try{await deleteAccount({current_password:deletePassword});window.location.replace('/')}catch(e){setError(e.message);setBusy(false)}}
  return <div className="page-wrap"><PageTitle eyebrow="YOUR ACCOUNT" title="Settings" copy="Manage access and your FitTrack account."/><div className="settings-stack"><section className="panel setting-panel"><div className="panel-heading"><div><span className="muted-label">SIGN-IN SECURITY</span><h2>Change password</h2></div><span className="stat-icon lime"><KeyRound size={16}/></span></div><p className="dashboard-note">Signed in as {account.email}. Use at least 12 characters with upper and lowercase letters and a number.</p><form className="form-stack setting-form" onSubmit={submit}>{hasPassword&&<label>Current password<input type="password" value={form.current_password} onChange={e=>setForm({...form,current_password:e.target.value})} required/></label>}<label>New password<input type="password" value={form.new_password} onChange={e=>setForm({...form,new_password:e.target.value})} minLength="12" required/></label><label>Confirm new password<input type="password" value={form.confirm_password} onChange={e=>setForm({...form,confirm_password:e.target.value})} minLength="12" required/></label>{error&&<div className="form-error">{error}</div>}<button className="button button-primary" disabled={busy}>{busy?'Saving?':'Update password'}</button></form></section><section className="panel setting-panel danger-panel"><div className="panel-heading"><div><span className="muted-label danger-label">IRREVERSIBLE</span><h2>Delete account</h2></div><span className="danger-icon"><X size={17}/></span></div><p className="dashboard-note">This permanently deletes your account, personal profile and activity history. Unclaimed legacy console records are not affected.</p>{hasPassword&&<label className="delete-confirm">Current password<input type="password" value={deletePassword} onChange={e=>setDeletePassword(e.target.value)} autoComplete="current-password"/></label>}<label className="delete-confirm">Type <b>DELETE</b> to confirm<input value={typed} onChange={e=>setTyped(e.target.value)} placeholder="DELETE"/></label>{error&&<div className="form-error">{error}</div>}<button className="button button-danger" disabled={typed!=='DELETE'||busy||(hasPassword&&!deletePassword)} onClick={remove}>Delete my account</button></section></div></div>
}

export default App
