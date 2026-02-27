# Koyeb + PostgreSQL Deployment

This project is ready for always-on hosting with Koyeb and PostgreSQL.

## 1. Create PostgreSQL

Use Neon (free tier) or any managed PostgreSQL provider.

Copy your connection string, for example:

`postgresql+psycopg2://USER:PASSWORD@HOST/DBNAME?sslmode=require`

## 2. Set environment variables locally (for validation)

Create/update `.env`:

```env
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST/DBNAME?sslmode=require
APP_BASE_URL=https://YOUR-KOYEB-APP.koyeb.app
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-gmail-app-password
MAIL_SENDER=your-email@gmail.com
SECRET_KEY=your-strong-secret
ADMIN_API_KEY=your-strong-admin-key
FLASK_DEBUG=0
SESSION_COOKIE_SECURE=true
```

## 3. Run pre-deploy checks

```powershell
.\.venv\Scripts\Activate.ps1
python scripts\predeploy_check.py
```

## 4. Deploy on Koyeb

1. New Web Service
2. GitHub repo: `Nupreeth/real-time-liveness-verification`
3. Builder: Dockerfile
4. Set all env vars from section 2
5. Deploy

## 5. Verify deployment

- Health check: `https://YOUR-KOYEB-APP.koyeb.app/health`
- Registration: `https://YOUR-KOYEB-APP.koyeb.app/register`
- Admin events:
  - `https://YOUR-KOYEB-APP.koyeb.app/admin/events?key=YOUR_ADMIN_API_KEY&limit=20`
