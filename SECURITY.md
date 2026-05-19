# Security Policy

## Sensitive Files

Never commit:

- `.env`
- Telegram API credentials.
- Telegram `*.session` files.
- JWT secrets, SMTP passwords, webhook tokens or notification keys.
- Database dumps, logs, exported datasets or backup archives.

## Production Hardening

- Set a strong `JWT_SECRET_KEY`.
- Restrict `CORS_ORIGINS` to trusted origins.
- Use HTTPS when exposing the frontend or API publicly.
- Limit server SSH access.
- Keep MySQL credentials scoped to this application.
- Review Pull Requests before merging into `main`.

## Reporting Issues

Open a private report to the repository owner when the issue involves credentials, session files, authentication bypass, data leakage, or production deployment risk.
