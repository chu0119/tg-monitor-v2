# Contributing

This repository uses `main` as the stable production branch.

## Required Workflow

1. Create a feature branch from `main`.
2. Commit focused changes with a clear message.
3. Open a Pull Request into `main`.
4. Wait for CI to pass.
5. Wait for owner review before merge.

Direct pushes to `main` should be avoided after branch protection is enabled.

## Local Checks

Backend:

```bash
cd backend
python -m compileall app
```

Frontend:

```bash
cd frontend
npm ci
npm run build
```

## Do Not Commit

- `.env` files.
- Telegram `*.session` files.
- Logs, backups, exports, uploads and databases.
- `node_modules/`, `frontend/dist/`, Python virtual environments.

## Pull Request Expectations

- Describe what changed and why.
- Mention deployment or migration steps when relevant.
- Include screenshots for dashboard or big-screen UI changes.
- Keep unrelated refactors out of production fixes.
