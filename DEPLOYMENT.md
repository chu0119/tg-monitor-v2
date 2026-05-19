# Deployment Guide

This document describes the recommended deployment, upgrade, backup and rollback flow for `tg-monitor-v2`.

## 1. System Requirements

- Linux server: Ubuntu 22.04/24.04, Debian 12, or compatible distribution.
- Python 3.11 or newer.
- Node.js 20 or newer.
- MySQL 8.x.
- A Telegram API ID and API Hash from <https://my.telegram.org/apps>.
- Optional proxy for Telegram connectivity.

## 2. Fresh Installation

```bash
git clone https://github.com/chu0119/tg-monitor-v2.git
cd tg-monitor-v2
cp .env.example .env
vim .env
bash install.sh
```

After installation:

```bash
./monitorctl.sh status
./health-check.sh
```

## 3. Manual Service Installation

```bash
cd tg-monitor-v2
bash install-services.sh
sudo systemctl enable tgmonitor-backend.service
sudo systemctl enable tgmonitor-frontend.service
sudo systemctl start tgmonitor-backend.service
sudo systemctl start tgmonitor-frontend.service
```

## 4. Upgrade Existing Deployment

Before upgrading, create a backup:

```bash
./monitorctl.sh backup
```

Then update the code:

```bash
git fetch origin
git checkout main
git pull --ff-only origin main

cd frontend
npm ci
npm run build

cd ../backend
source venv/bin/activate
pip install -r requirements.txt

sudo systemctl restart tgmonitor-backend.service
sudo systemctl restart tgmonitor-frontend.service
```

Verify:

```bash
curl -f http://127.0.0.1:8000/health
curl -f http://127.0.0.1:3000/
```

## 5. Backup and Restore

Data that must be backed up:

- MySQL database.
- `backend/sessions/` Telegram session files.
- `.env` runtime configuration.
- Optional uploads and exports if used operationally.

Data that should not be committed to Git:

- `.env`
- `backend/sessions/`
- `logs/`
- `exports/`
- `backups/`
- `frontend/dist/`
- `node_modules/`

## 6. Rollback

If a deployment fails:

```bash
git log --oneline -5
git checkout <known-good-commit>

cd frontend
npm ci
npm run build

sudo systemctl restart tgmonitor-backend.service
sudo systemctl restart tgmonitor-frontend.service
```

If data was changed, restore the database and session files from the backup created before upgrade.

## 7. Production Notes

- Set `JWT_SECRET_KEY` to a long random value.
- Restrict `CORS_ORIGINS` to trusted domains in public deployments.
- Protect `main` in GitHub and merge changes through Pull Requests.
- Keep server `.env` and Telegram session files off the repository.
- Monitor `/health` and service logs after every upgrade.
