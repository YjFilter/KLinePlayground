# Vercel and Neon Deployment Handoff

## Outcome
- Production alias: `https://kline-playground-seven.vercel.app`.
- Project: `yjfilters-projects/kline-playground`.
- Deployment: `dpl_HTXGqkiu5uVqEL6kWEn8weWE6HTR`.
- Neon resource: `neon-claret-mirror`.

## Implementation
- `vercel.json` defines the Flask service and root rewrite.
- `pyproject.toml` defines cloud Python dependencies.
- `.vercelignore` excludes runtime, local users, tests, secrets, and desktop-only files.
- `backend/cloud_state.py` archives user directories to PostgreSQL and restores them on cold starts.
- Successful mutations save the affected user archive to Neon.
- Production and Preview use HTTP Basic Auth; health monitoring stays public.
- Credentials are stored outside the repository at `D:\Personal\Temp\kline-vercel-credentials.txt`.

## Data
- The local `yj` directory was uploaded to Neon.
- Test user archives were removed; cloud inventory contains only `yj`.

## Verification
- Full suite: 675 passed and 66 subtests passed.
- JavaScript syntax, Python compileall, and diff check passed.
- Public health reports cloud enabled, ready, one user, and no error.
- Real Neon smoke covered user creation, BTCUSDT start, next candle, persistence, deletion, and cloud row removal.

## Constraint
- This mainland network resolves `*.vercel.app` to incorrect IPs. Use a custom domain or VPN for stable direct access.

## Safety and Rollback
- No commit was created; existing uncommitted changes remain.
- `.runtime/` was not touched or uploaded.
- Roll back the application with `npx vercel@latest rollback` or the Vercel dashboard.
- Do not remove Neon before confirming a current local copy of `users/yj`.
