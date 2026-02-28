---
title: Real-Time Liveness Verification
emoji: 🤖
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# Eye Blink Verification System

Email-gated liveness verification built with Flask, MediaPipe Face Mesh, and PostgreSQL.

This system validates two things before marking a user as verified:
1. The user owns the registered email (tokenized email link verification).
2. A live person is present on camera (blink sequence: `OPEN -> CLOSED -> OPEN` + frame capture).

## What this project does well

- Clear layered architecture (`routes`, `services`, `models`, `utils`).
- Real liveness pipeline (face alignment + EAR eye-state classification).
- Defensive checks (no face, multiple faces, poor alignment, timeout).
- Persistent workflow state in PostgreSQL (`PENDING`, `VERIFIED`, `FAILED`).
- Production-minded defaults (security headers, env-based config, request size limits).
- Clean UI/UX with guided steps and status feedback.

## Tech stack

- Python 3.11
- Flask
- PostgreSQL
- SQLAlchemy Core
- MediaPipe Face Mesh
- OpenCV
- NumPy
- Cloudinary (optional persistent capture storage)
- Vanilla JavaScript (Webcam API)
- HTML/CSS (Jinja templates)
- SMTP (Gmail App Password)

## Project structure

```text
eye_verification_system/
├── app.py
├── config.py
├── requirements.txt
├── .env.example
├── .gitignore
├── instance/
│   └── database.db
├── models/
│   └── user.py
├── routes/
│   ├── auth_routes.py
│   ├── camera_routes.py
│   └── __init__.py
├── services/
│   ├── face_detection.py
│   ├── eye_detection.py
│   ├── liveness_check.py
│   └── email_service.py
├── utils/
│   ├── image_utils.py
│   ├── token_utils.py
│   └── constants.py
├── templates/
│   ├── base.html
│   ├── register.html
│   ├── verify_email.html
│   ├── camera.html
│   └── result.html
├── static/
│   ├── js/camera.js
│   ├── css/style.css
│   └── uploads/
│       ├── open_eye/.gitkeep
│       └── closed_eye/.gitkeep
└── README.md
```

## Database schema

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    verification_token VARCHAR(512),
    status VARCHAR(20) DEFAULT 'PENDING'
);

CREATE TABLE verification_events (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL,
    reason VARCHAR(500) DEFAULT '',
    open_captured INTEGER DEFAULT 0,
    closed_captured INTEGER DEFAULT 0,
    open_capture_ref VARCHAR(1024) DEFAULT '',
    closed_capture_ref VARCHAR(1024) DEFAULT '',
    created_at VARCHAR(64) NOT NULL
);
```

## End-to-end flow

1. User submits email at `/register`.
2. App creates/refreshes user token in PostgreSQL.
3. Verification email is sent with: `/verify?token=...`.
4. User must click that link to proceed (token-only gate).
5. User starts liveness check; camera sends frames automatically.
6. Backend validates:
   - exactly one face
   - face alignment and distance
   - frame sharpness
   - eye state (`OPEN`/`CLOSED`) using EAR
7. Best open-eye and closed-eye frames are saved and can be pushed to persistent storage.
8. Status is updated:
   - `VERIFIED` when both captures succeed
   - `FAILED` on timeout or session failure
9. Event audit entry is stored in `verification_events`.

## Notes for reviewers

- This is a from-scratch implementation focused on practical liveness verification flow.
- Logic is modular and intentionally easy to explain in code walkthroughs.
- UI is intentionally simple, clean, and task-oriented.

## Setup

1. Create virtual environment and activate:
   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. Install dependencies:
   ```powershell
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
3. Create local env from template:
   ```powershell
   Copy-Item .env.example .env
   ```
4. For hosted deployment, create a separate production file:
   ```powershell
   Copy-Item .env.production.example .env.production
   ```
   Keep `.env.production` private and never commit it.
5. Set PostgreSQL connection string:
   ```env
   DATABASE_URL=postgresql+psycopg2://<user>:<password>@<host>:5432/<db_name>
   ```
6. Run:
   ```powershell
   python app.py
   ```
7. Open:
    - `http://127.0.0.1:5000/register`

## Environment file strategy

- `.env.example`: GitHub-safe local template.
- `.env.production.example`: GitHub-safe production template.
- `.env`: local secrets (ignored by git).
- `.env.production`: deployment secrets (ignored by git).

To run checks against production env locally:

```powershell
$env:ENV_FILE=".env.production"
python scripts\predeploy_check.py
Remove-Item Env:ENV_FILE
```

## Use on other devices

1. Run app on host machine:
   ```powershell
   python app.py
   ```
2. Find host LAN IP (example `10.0.11.46`).
3. Open from another device on same network:
   - `http://10.0.11.46:5000/register`
4. Verification emails now auto-use request host, so links work across devices.
5. If a browser hits `https://10.0.11.46:5000` by default, force `http://` explicitly.

## Cloud deploy (recommended no-card path: Hugging Face Spaces)

Vercel is not ideal for this app because it relies on long-running Python CV processing
with native dependencies (`opencv` + `mediapipe`) and persistent backend state.

Use Hugging Face Spaces (Docker) + Neon PostgreSQL for a no-card deployment path.

### Deploy steps

1. Push this project to GitHub.
2. Create a new Hugging Face Space with SDK = **Docker**.
3. Upload/push repo code to the Space.
4. Add required Space secrets:
   - `DATABASE_URL`
   - `APP_BASE_URL` (Space URL like `https://<space>.hf.space`)
   - `MAIL_USERNAME`
   - `MAIL_PASSWORD`
   - `MAIL_SENDER`
   - `RESEND_API_KEY` (recommended for hosted delivery reliability)
   - `RESEND_FROM_EMAIL` (default `onboarding@resend.dev` for testing)
   - `CLOUDINARY_CLOUD_NAME` (optional for persistent image storage)
   - `CLOUDINARY_API_KEY` (optional)
   - `CLOUDINARY_API_SECRET` (optional)
   - `SECRET_KEY`
   - `ADMIN_API_KEY`
5. Deploy.
6. Test:
   - `https://<space>.hf.space/health`
   - register and verify flow from another device.

### Start command used

```text
waitress-serve --host=0.0.0.0 --port=${PORT:-7860} app:app
```

Deployment guides:
- [DEPLOY_HF_SPACES.md](DEPLOY_HF_SPACES.md)
- [DEPLOY_KOYEB.md](DEPLOY_KOYEB.md)

## Gmail SMTP notes

- Use Gmail App Password (16-char), not your normal account password.
- Required keys in `.env`:
  - `MAIL_USERNAME`
  - `MAIL_PASSWORD`
  - `MAIL_SENDER`
  - `APP_BASE_URL`

## Key config options

- `DATABASE_URL` (PostgreSQL DSN used by SQLAlchemy)
- `FRAME_CAPTURE_INTERVAL_MS` (default `200`)
- `LIVENESS_TIMEOUT_SECONDS` (default `30`)
- `MAX_CONTENT_LENGTH` (default `4MB`)
- `SESSION_COOKIE_SECURE` (`true` in HTTPS deployments)
- `LOG_LEVEL` (`INFO`, `DEBUG`, `WARNING`, etc.)
- `ADMIN_API_KEY` (required for admin reporting endpoints)

## Production run (example)

Use a production WSGI server instead of Flask dev server:

```powershell
waitress-serve --host=0.0.0.0 --port=5000 app:app
```

## Troubleshooting

- If app says eye detection model unavailable, check MediaPipe:
  ```powershell
  python -c "import mediapipe as mp; print(mp.__version__, hasattr(mp, 'solutions'))"
  ```
  Expected for this project: `0.10.14` and `True`.
- If not, reinstall:
  ```powershell
  pip install --force-reinstall mediapipe==0.10.14
  ```

## Quick checks

Health endpoint:
```text
GET /health
```

Query users (PostgreSQL via SQLAlchemy):
```powershell
python -c "from sqlalchemy import create_engine,text; from config import Config; e=create_engine(Config.DATABASE_URL); rows=e.connect().execute(text('SELECT id,email,status,verification_token FROM users ORDER BY id DESC LIMIT 20')); [print(dict(r._mapping)) for r in rows]"
```

Recent event logs:
```powershell
python -c "from sqlalchemy import create_engine,text; from config import Config; e=create_engine(Config.DATABASE_URL); rows=e.connect().execute(text('SELECT id,email,status,reason,open_capture_ref,closed_capture_ref,created_at FROM verification_events ORDER BY id DESC LIMIT 20')); [print(dict(r._mapping)) for r in rows]"
```

Admin API (JSON):
```text
GET /admin/events?key=YOUR_ADMIN_API_KEY&limit=100
```

Admin export (CSV):
```text
GET /admin/events.csv?key=YOUR_ADMIN_API_KEY&limit=500
```
