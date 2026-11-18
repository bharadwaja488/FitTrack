# FitTrack 3.0 — personal fitness accounts

The web application is a personal account-based React + Flask application. The original Python/MySQL console application remains available through `python main.py`; see [README.md](README.md).

## 1. Configure local environment

Do not replace or inspect an existing root `.env`. For a new local setup, copy `.env.example` to `.env` and set credentials for a disposable development database created for this purpose. The example database name is not guaranteed to exist. Never reuse production credentials or point development/tests at production data. Configure production credentials independently in the deployment environment. Generate a private local `SECRET_KEY`. Use `COOKIE_SECURE=false` for local HTTP; production requires `COOKIE_SECURE=true` behind HTTPS.

```dotenv
SECRET_KEY=replace-with-a-long-random-secret
FRONTEND_URL=http://localhost:5174
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:5000/api/auth/google/callback
MAIL_SERVER=
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_PORT=587
MAIL_USE_TLS=true
COOKIE_SECURE=false
RATELIMIT_STORAGE_URI=memory://
```

Use `localhost` consistently for frontend and backend so browser cookies are same-site. The default Google and email settings are empty. Google sign-in and email reset are visibly unavailable until real credentials are configured.

For local MySQL, the example uses port 3306 and no TLS verification. Do not copy these local database settings into production. Production startup requires database TLS certificate and hostname verification, shared rate-limit storage, a configured trusted proxy count, a stable secret key, HTTPS cookies, and public HTTPS frontend origins.

`RATELIMIT_STORAGE_URI=memory://` is for local development only. Production validation runs with `FITTRACK_ENV=production` and intentionally does not load the root `.env`; a value saved only there will not reach the validator. For local production-shaped validation, inject variables into the same PowerShell process that launches Python using your approved local secret store. Check whether the Redis variable is present without displaying it:

```powershell
if ([string]::IsNullOrWhiteSpace($env:RATELIMIT_STORAGE_URI)) { throw 'RATELIMIT_STORAGE_URI is missing from this PowerShell process.' }
```

Use the Upstash TCP connection URL, not its REST URL/token pair. Production requires an authenticated `rediss://` URL with a hostname and valid port; query strings and fragments are rejected. The validator reports missing or invalid variable names and safe corrections without printing any configured values.


## 2. Database migrations

The repository contains these ordered migration files. Review each SQL file and the runner before applying any migration. Do not infer that a migration has run based on this documentation. Use a disposable database for local development. Production migration requires a separately approved procedure, a verified target, and a tested backup/restore plan. Never run migrations against production as part of local setup.

- `0000_legacy_base_schema.sql` — creates the legacy base tables if absent.
- `0001_accounts_and_personal_profiles.sql` — adds account ownership and personal profiles.
- `0002_owned_profiles_require_activity_level.sql` — adds the activity-level requirement for owned profiles.
- `0003_fitness_goals_and_weight_history.sql` — adds goals and weight history.
- `0004_nutrition_records.sql` — adds nutrition records.
- `0005_nutrition_source_data.sql` — adds nutrition source data.
- `0006_advanced_activity_tracking.sql` — adds advanced activity tracking fields.

After verifying the database target and taking an appropriate backup, the local runner can be invoked with:

```powershell
cd backend
..\.venv\Scripts\python.exe migrate.py
```

For production, the runner deliberately ignores root `.env`. Supply DB settings as server-side environment variables, set `FITTRACK_EXPECTED_DB_HOST` and `FITTRACK_EXPECTED_DB_NAME` to the exact intended target, and pass `--confirm-production` only after reviewing the target and backup. The production connection requires verified TLS. No migration runs automatically when the web service starts.

The runner checks expected schema objects and records a version after verification. Existing profiles require a deliberate account-claim process. Do not assume a database is current without checking its migration records and schema.


Legacy-profile claim policy: rows stay unclaimed until an operator independently verifies the person requesting a claim. Never link by matching a name or email from the old profile. For an approved claim, use a transaction that locks both account and profile, requires `users.account_id IS NULL`, verifies the account has no profile, then sets only that profile?s `account_id`; retain an audit record of who approved the link. The foreign key and unique key reject invalid or duplicate ownership. No automatic claim endpoint is exposed.

## 3. Start the application

Backend (from project root):

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
cd backend
..\.venv\Scripts\python.exe run.py
```

Frontend in another PowerShell window:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Open `http://localhost:5174`. Backend health check: `http://localhost:5000/api/health`. The frontend base URL can be changed via `frontend/.env` using `VITE_API_URL`.

## Vercel and Render configuration

Configure Vercel with `frontend/` as the project root, `npm run build` as the build command, and `dist` as the output directory. The checked-in `vercel.ts` requires `RENDER_API_ORIGIN` as an HTTPS origin with no path; it creates the `/api/*` proxy before the SPA fallback. Production frontend requests use same-origin `/api` so the host-only secure session cookie and CSRF header remain on the Vercel site. Do not set `VITE_API_URL` to the Render hostname in production.

Configure Render with `backend/` as the root directory, install `requirements.txt`, and start with `gunicorn --bind 0.0.0.0:$PORT run:app`. In the Render Dashboard, open the `fittrack-api-staging` service's **Environment** page and configure the `sync: false` variables from `render.yaml` there. Set `FRONTEND_URL` and `FRONTEND_ORIGINS` to `https://fittrack-chi-gold.vercel.app`. Set `RATELIMIT_STORAGE_URI` to the authenticated TCP URL copied from Upstash **Connect > TCP**, in the form `rediss://default:<token>@<host>:6379`; do not use the REST URL/token pair or add TLS query parameters. Keep the URL private. Configure the remaining secret values there, including `SECRET_KEY`, database credentials, and the mounted `DB_SSL_CA` path. The Blueprint fixes `FITTRACK_ENV=production`, `FLASK_DEBUG=false`, `COOKIE_SECURE=true`, `DB_PORT=4000`, the staging database name, database TLS verification, timeouts, and `TRUSTED_PROXY_HOPS=0`. FitTrack does not trust `X-Forwarded-For` or `X-Forwarded-Proto`. On Render, the limiter uses Render's edge-overwritten `CF-Connecting-IP`, falling back to the socket peer if invalid. A request proxied by Vercel can appear to Render as a Vercel edge address, so those users may share rate-limit buckets. Do not increase the proxy hop count; the public Render origin is reachable directly and a longer forwarded chain can be spoofed.

In Vercel project settings, set `RENDER_API_ORIGIN` to `https://fittrack-oeh1.onrender.com` for the required deployment environments. The frontend origin is `https://fittrack-chi-gold.vercel.app`; the backend proxy origin is the Render URL above.

The repository includes `render.yaml` for a staging-only Render Blueprint with the health check path set to `/api/health` and automatic deploys disabled. Run `backend/validate_production.py` to validate provider environment settings without opening service connections. Use `backend/check_staging_db.py` for a read-only staging TiDB/TLS connection check and `backend/migrate_staging.py --confirm-staging` only after reviewing the target and obtaining approval. These staging tools require `FITTRACK_ENV=production` so they do not load the root `.env`. The concise provider setup and approval checklist is [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md).

Optional Google OAuth requires `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REDIRECT_URI` set to the Vercel proxied callback URL `/api/auth/google/callback`, registered with Google. Optional SMTP reset requires `MAIL_SERVER`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_PORT`, and `MAIL_USE_TLS=true`. Render Free blocks outbound SMTP ports, so password reset needs a different delivery path or a hosting plan that permits SMTP.

Render Free services sleep after idle time, may restart, use ephemeral filesystems, and are not intended for production workloads. They are suitable for a demo/staging evaluation, not an availability commitment. Use a production-capable service tier for a public release.

After an approved staging deployment and migration, run `python scripts/smoke_deployment.py --frontend-url https://<staging-vercel-domain>` to check proxied API health, provider/CSRF endpoints, cache headers, and direct SPA route refresh. The script performs GET requests only; account creation and authenticated flows require a separately approved staging test.

## Google OAuth setup

1. In Google Cloud Console, create or select a project and configure the OAuth consent screen.
2. Create an OAuth 2.0 Web application client.
3. Add `http://localhost:5000/api/auth/google/callback` as an authorized redirect URI.
4. Put its client ID and secret in the root `.env` as `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`; set `GOOGLE_REDIRECT_URI` to the same exact URI.
5. Restart Flask. The app uses Authlib OpenID Connect (`openid email profile`), checks state and nonce, validates the ID token and requires Google’s verified-email claim. A verified matching email links to the existing account. No OAuth credentials are included in the repository.

## Email password reset

Set `MAIL_SERVER`, `MAIL_USERNAME`, `MAIL_PASSWORD`, and optionally `MAIL_PORT` / `MAIL_USE_TLS`. Reset links expire after 30 minutes, are signed, and become invalid after use. Without SMTP values, the endpoint returns a neutral response and the UI explains that email delivery is not configured.

## Account and privacy behavior

- Registration stores an Argon2id password hash. Passwords require 12–128 characters with uppercase, lowercase, and a number. Login/registration/reset errors are rate-limited.
- Registration uses the same response for new and duplicate email addresses. After submitting the form, sign in to continue to profile onboarding.
- Sessions use signed HttpOnly, SameSite=Lax cookies, a 12-hour expiration, CSRF tokens for mutations, and a database session version for revocation.
- Each account owns at most one profile. Profile, activity, history, and dashboard queries filter by the authenticated account from the session. The API ignores supplied `user_id` / `account_id` for ownership.
- Account deletion requires confirmation and current password for password accounts, and deletes only that account’s activity/profile/account in a transaction. Unclaimed console records stay untouched.
- The web application calculates BMI as weight in kilograms divided by height in metres squared, BMR with the Mifflin–St Jeor equation, and TDEE by multiplying BMR by the selected activity factor (1.2, 1.375, 1.55, 1.725, or 1.9). The original console application remains separate and estimates daily calories as BMR ×1.2; it does not use an activity-level multiplier.
- HTTP-only local cookies are not marked Secure on localhost. Enable `COOKIE_SECURE=true` for HTTPS deployment. Flask-Limiter uses in-memory storage by default for local development; configure a shared storage URI for a multi-worker deployment.

Nutrition tracking and food search have been removed. Existing nutrition tables, migration history, and saved records are retained unchanged.

## Pages

Landing, Sign Up, Login, Forgot Password, Reset Password, Onboarding, Overview, My Profile, Health Metrics, Activity Tracking, My History, Settings. The old People/Workspace/profile-picker UI and public user browsing API are removed. The console CLI remains available; profiles it creates remain unclaimed unless a deliberate claim workflow is built.

## API

- Auth: `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`, `GET /api/auth/providers`, `GET /api/auth/csrf`, Google start/callback, `POST /api/auth/forgot-password`, `POST /api/auth/reset-password`
- Personal: `GET/PUT /api/profile`, `GET/POST /api/fitness`, `GET /api/fitness/history`
- Activity: `PUT/DELETE /api/fitness/<record_id>`, `GET/PUT /api/fitness/step-goal`; fitness history accepts optional `start` and `end` dates. Daily steps, cardio sessions, and named workouts share `fitness_records` and are scoped to the signed-in account.
- Dashboard: `GET /api/dashboard/summary`, `GET /api/dashboard/activity?period=week|month`
- Settings: `PUT /api/settings/password`, `DELETE /api/settings/account`

Private routes require a valid session and validate ownership on the server. Success uses `{ "data": ... }`; errors use `{ "error": { "code", "message" } }`.

## Verification

```powershell
$env:FITTRACK_RUN_DB_TESTS="1"
.\.venv\Scripts\python.exe -m pytest backend\tests -q
cd frontend
npm.cmd run build
npm.cmd audit
```

The backend suite covers calculation formulas, activity and goal validation, password strength, CSRF enforcement, anonymous-access rejection, and a MySQL-backed two-account activity isolation flow. Database-free tests run normally. The integration test is skipped unless `FITTRACK_RUN_DB_TESTS=1`; when enabled, it requires explicit `FITTRACK_TEST_DB_NAME`, `FITTRACK_TEST_DB_HOST`, `FITTRACK_TEST_DB_USER`, `FITTRACK_TEST_DB_PASSWORD`, and `FITTRACK_TEST_DB_CONFIRM=I_CONFIRM_THIS_IS_A_DISPOSABLE_TEST_DATABASE`. The database name must contain a separate `test` token and cannot contain `prod`, `production`, or `live`. It connects only with these test-specific values, verifies `SELECT DATABASE()` matches the configured test database, then creates and removes temporary accounts. It never falls back to `DB_NAME` from `.env`. Do not use a production database. Google OAuth cannot complete until real Google client credentials are configured; with credentials absent, the API reports the provider as unavailable.

Gunicorn and production configuration are implemented, and `frontend/vercel.ts` provides the Vercel API proxy configuration. Staging deployment has not yet been validated. Linux Gunicorn worker/runtime verification and TiDB staging migrations remain pending. Production deployment is not complete; finish staging startup, database, proxy, authentication, and migration validation before considering a production release.
