# Eye Blink Verification System

Email-gated liveness verification built with Flask, MediaPipe Face Mesh, and SQLite.

This system validates two things before marking a user as verified:
1. The user owns the registered email (tokenized email link verification).
2. A live person is present on camera (blink sequence: `OPEN -> CLOSED -> OPEN` + frame capture).

## What this project does well

- Clear layered architecture (`routes`, `services`, `models`, `utils`).
- Real liveness pipeline (face alignment + EAR eye-state classification).
- Defensive checks (no face, multiple faces, poor alignment, timeout).
- Persistent workflow state in SQLite (`PENDING`, `VERIFIED`, `FAILED`).
- Production-minded defaults (security headers, env-based config, request size limits).
- Clean UI/UX with guided steps and status feedback.

## Tech stack

- Python 3.11
- Flask
- SQLite
- MediaPipe Face Mesh
- OpenCV
- NumPy
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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE,
    verification_token TEXT,
    status TEXT DEFAULT 'PENDING'
);

CREATE TABLE verification_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT DEFAULT '',
    open_captured INTEGER DEFAULT 0,
    closed_captured INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);
```

## End-to-end flow

1. User submits email at `/register`.
2. App creates/refreshes user token in SQLite.
3. Verification email is sent with: `/verify?token=...`.
4. User must click that link to proceed (token-only gate).
5. User starts liveness check; camera sends frames automatically.
6. Backend validates:
   - exactly one face
   - face alignment and distance
   - frame sharpness
   - eye state (`OPEN`/`CLOSED`) using EAR
7. Best open-eye and closed-eye frames are saved.
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
3. Create `.env` from `.env.example` and set your values.
4. Run:
   ```powershell
   python app.py
   ```
5. Open:
    - `http://127.0.0.1:5000/register`

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

## Cloud deploy (recommended: Render)

Vercel is not ideal for this app because it relies on long-running Python CV processing
with native dependencies (`opencv` + `mediapipe`) and persistent storage for SQLite/uploads.
Use Render (Docker) for stable hosting.

### Deploy steps

1. Push this project to GitHub.
2. In Render, click **New +** -> **Blueprint**.
3. Select your GitHub repo (Render will detect `render.yaml`).
4. Set required environment values in Render dashboard:
   - `APP_BASE_URL` (use your Render URL, e.g. `https://your-app.onrender.com`)
   - `MAIL_USERNAME`
   - `MAIL_PASSWORD`
   - `MAIL_SENDER`
   - `ADMIN_API_KEY`
5. Deploy.
6. Test:
   - `https://your-app.onrender.com/health`
   - register and verify flow from another device.

### Start command used

```text
waitress-serve --host=0.0.0.0 --port=5000 app:app
```

## Gmail SMTP notes

- Use Gmail App Password (16-char), not your normal account password.
- Required keys in `.env`:
  - `MAIL_USERNAME`
  - `MAIL_PASSWORD`
  - `MAIL_SENDER`
  - `APP_BASE_URL`

## Key config options

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

Query users:
```powershell
python -c "import sqlite3; c=sqlite3.connect('instance/database.db'); c.row_factory=sqlite3.Row; [print(dict(r)) for r in c.execute('SELECT id,email,status,verification_token FROM users ORDER BY id DESC')]"
```

Recent event logs:
```powershell
python -c "import sqlite3; c=sqlite3.connect('instance/database.db'); c.row_factory=sqlite3.Row; [print(dict(r)) for r in c.execute('SELECT id,email,status,reason,created_at FROM verification_events ORDER BY id DESC LIMIT 20')]"
```

Admin API (JSON):
```text
GET /admin/events?key=YOUR_ADMIN_API_KEY&limit=100
```

Admin export (CSV):
```text
GET /admin/events.csv?key=YOUR_ADMIN_API_KEY&limit=500
```
