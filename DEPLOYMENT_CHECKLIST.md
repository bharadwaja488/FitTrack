# FitTrack staging deployment checklist

This checklist prepares a staging release only. It does not authorize deployment, database changes, or production use. Never use the compromised TiDB password or Flask SECRET_KEY; rotate both and enter replacement credentials only in provider secret settings.

## One-time provider setup

- [ ] **TiDB Cloud Console > Clusters > staging cluster > Connect / SQL Editor:** create a dedicated staging cluster, then create the database with CREATE DATABASE fittrack_staging; using only that cluster. Copy its hostname; use port 4000; restrict the public endpoint firewall to the Render staging egress addresses. Download the CA certificate from TiDB's connection instructions. Do not run this SQL against any existing or production cluster.
- [ ] **Upstash Console > Redis database > Connect > TCP:** create/select a separate staging database and copy its authenticated TLS connection URL. Use the TCP `rediss://` URL, not the REST URL/token pair.
- [ ] **Render Dashboard > Blueprints > New Blueprint Instance:** select this repository and review render.yaml. Keep the fittrack-api-staging service; do not create a production service from this manifest. Set the sync:false fields in the service's Environment page, including `RATELIMIT_STORAGE_URI` using the copied Upstash TCP URL. Keep that value private; do not paste it into logs or chat. Put the TiDB CA file in Render Secret Files and set DB_SSL_CA to its mounted path. Configure `FRONTEND_URL` and `FRONTEND_ORIGINS` as `https://fittrack-chi-gold.vercel.app`. Keep TRUSTED_PROXY_HOPS=0; FitTrack trusts no X-Forwarded-For or X-Forwarded-Proto chain because the public Render origin is directly reachable. On Render, rate limiting uses the edge-overwritten CF-Connecting-IP header and falls back to the socket peer if invalid. Through Vercel, this can identify Vercel's edge rather than the browser, so rate-limit buckets may aggregate. Do not raise the hop count to recover browser IPs; that would trust a spoofable chain.
- [ ] **Vercel Dashboard > Project Settings > Environment Variables:** set `RENDER_API_ORIGIN` to `https://fittrack-oeh1.onrender.com` for the approved deployment environments. The browser-facing frontend origin is `https://fittrack-chi-gold.vercel.app`. Do not promote a deployment or set production domains before approval.

## Read-only preflight

Run from the repository root in Windows PowerShell, with the backend virtual environment and staging credentials already configured in the process environment or provider. Production mode deliberately skips root `.env`; variables stored there are not loaded. For local validation, populate the process environment through an approved local secret store and check presence without displaying values:

```powershell
$fittrackPython = Join-Path (Get-Location) (Join-Path '.venv' (Join-Path 'Scripts' 'python.exe'))
$env:FITTRACK_ENV = 'production'
if ([string]::IsNullOrWhiteSpace($env:RATELIMIT_STORAGE_URI)) { throw 'RATELIMIT_STORAGE_URI is missing from this PowerShell process.' }
& $fittrackPython (Join-Path 'backend' 'validate_production.py')
if ($LASTEXITCODE -ne 0) { throw 'Production configuration validation failed; staging checks and migration were not run.' }
& $fittrackPython (Join-Path 'backend' 'check_staging_db.py')
if ($LASTEXITCODE -ne 0) { throw 'Staging database validation failed; migration was not run.' }
```

The first command validates production-shaped settings without connecting to MySQL or Redis. It reports missing or invalid variable names with safe corrections and never prints configured values. The Redis setting must be an authenticated Upstash TCP `rediss://` URL with a hostname and valid port; query and fragment options are not accepted. The second command makes a TLS-verified, read-only TiDB check. Each native command is followed immediately by an exit-code check. Failure stops the block. The database check requires exactly DB_NAME=fittrack_staging, matching FITTRACK_EXPECTED_DB_NAME, matching DB_HOST/FITTRACK_EXPECTED_DB_HOST, port 4000, a readable CA file, and certificate plus hostname verification. The tools do not load root .env when FITTRACK_ENV=production.

## Proxy and rate-limit IP policy

The configured value is deliberately TRUSTED_PROXY_HOPS=0. FitTrack does not install ProxyFix and ignores X-Forwarded-For and X-Forwarded-Proto. On Render, the rate limiter accepts only a syntactically valid CF-Connecting-IP, which Render documents as overwritten by its Cloudflare edge; otherwise it uses the socket peer. Vercel-to-Render requests may therefore be keyed by the Vercel edge address. This is the safe behavior for a public Render origin without a private or authenticated Vercel-to-Render channel. Do not guess or increase a hop count. The production preflight command above validates that the configured value is exactly zero; targeted backend tests verify missing/invalid/accepted values and spoofed-header behavior.

## Separately approved staging migration

Run this block only after migration approval. It repeats both preflights immediately before migration and stops on either failure. The final prompt is an additional operator confirmation.

```powershell
$fittrackPython = Join-Path (Get-Location) (Join-Path '.venv' (Join-Path 'Scripts' 'python.exe'))
$env:FITTRACK_ENV = 'production'
& $fittrackPython (Join-Path 'backend' 'validate_production.py')
if ($LASTEXITCODE -ne 0) { throw 'Production configuration validation failed; migration was not run.' }
& $fittrackPython (Join-Path 'backend' 'check_staging_db.py')
if ($LASTEXITCODE -ne 0) { throw 'Staging database validation failed; migration was not run.' }
$migrationApproval = Read-Host 'Type APPLY FITTRACK STAGING to confirm the reviewed staging migration'
if ($migrationApproval -cne 'APPLY FITTRACK STAGING') { throw 'Staging migration was not approved.' }
& $fittrackPython (Join-Path 'backend' 'migrate_staging.py') --confirm-staging
if ($LASTEXITCODE -ne 0) { throw 'Staging migration failed; stop and inspect its recovery report.' }
```

The migration tool requires --confirm-staging, verifies the exact target and TLS settings, and never retries automatically. On failure, stop and inspect schema_migrations and the actual schema before determining a recovery plan.

## Post-deployment smoke check

After approved staging deployment and migration, run from the repository root in Windows PowerShell:

```powershell
$fittrackPython = Join-Path (Get-Location) (Join-Path '.venv' (Join-Path 'Scripts' 'python.exe'))
$stagingFrontendUrl = Read-Host 'Staging Vercel HTTPS origin'
& $fittrackPython (Join-Path 'scripts' 'smoke_deployment.py') --frontend-url $stagingFrontendUrl
if ($LASTEXITCODE -ne 0) { throw 'Staging smoke checks failed.' }
```

The smoke test uses GET requests only. It checks proxied API health, authentication-provider and CSRF bootstrap responses, API no-store headers, and direct refresh of /app/activity. It rejects non-public destinations and redirects, and does not register accounts, log in, or change user data. Perform registration/login, cookie persistence, CSRF mutation, logout, account isolation, and Google/email flows only as separately approved staging validation.

## Approval gates

- [ ] Rotate compromised TiDB password and SECRET_KEY; use distinct staging credentials.
- [ ] Approve provider resource creation and any plan/cost choice.
- [ ] Review and approve staging migration plan before running the separate migration block.
- [ ] Review smoke results and approve any broader staging account-flow tests.
- [ ] Obtain separate approval before production migration, promotion, or deployment.
