# Deploy on Hugging Face Spaces (No Card Path)

This guide deploys the app to a public URL that works even when your laptop is off.

## 1. Prerequisites

1. GitHub repo is up to date.
2. Neon PostgreSQL database is created.
3. Gmail App Password is ready.

## 2. Create Space

1. Sign in at `https://huggingface.co/`.
2. Click **New Space**.
3. Space name: `real-time-liveness-verification` (or your choice).
4. SDK: **Docker**.
5. Visibility: **Public**.
6. Click **Create Space**.

## 3. Upload code

Option A (UI):
1. Open your Space.
2. Go to **Files**.
3. Upload project files (same as GitHub repo).

Option B (recommended):
1. Link/push from your GitHub repo to the Space repo.

## 4. Add Secrets (Space Settings)

Open **Settings -> Repository secrets** and add:

- `DATABASE_URL`
- `APP_BASE_URL`
- `MAIL_USERNAME`
- `MAIL_PASSWORD`
- `MAIL_SENDER`
- `RESEND_API_KEY`
- `RESEND_FROM_EMAIL` (`onboarding@resend.dev` for testing)
- `SECRET_KEY`
- `ADMIN_API_KEY`
- `FLASK_DEBUG` = `0`
- `SESSION_COOKIE_SECURE` = `true`
- `LOG_LEVEL` = `INFO`
- `CLOUDINARY_CLOUD_NAME` (optional)
- `CLOUDINARY_API_KEY` (optional)
- `CLOUDINARY_API_SECRET` (optional)
- `CLOUDINARY_FOLDER` (optional, default `eye-verification`)

Set `APP_BASE_URL` to your Space URL:

`https://<your-space-name>.hf.space`

## 5. Deploy and verify

1. Wait for Space build to finish.
2. Open:
   - `https://<your-space-name>.hf.space/health`
3. Run full flow:
   - `/register`
   - open email link
   - camera liveness
   - verify DB updates

## 6. Notes

1. Free Spaces may sleep after inactivity and wake on next request.
2. Keep all real secrets only in Space secrets and local private `.env` files.
3. Do not commit `.env` or `.env.production`.
