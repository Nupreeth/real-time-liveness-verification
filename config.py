import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DEFAULT_ENV_FILE = ".env"
env_file = os.getenv("ENV_FILE", DEFAULT_ENV_FILE)
env_path = Path(env_file)
if not env_path.is_absolute():
    env_path = Path(BASE_DIR) / env_path
load_dotenv(env_path)


def _env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    DEBUG = _env_bool("FLASK_DEBUG", default=False)

    DATABASE_PATH = os.getenv(
        "DATABASE_PATH",
        os.path.join(BASE_DIR, "instance", "database.db"),
    )
    DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATABASE_PATH}")
    OPEN_EYE_UPLOAD_DIR = os.getenv(
        "OPEN_EYE_UPLOAD_DIR",
        os.path.join(BASE_DIR, "static", "uploads", "open_eye"),
    )
    CLOSED_EYE_UPLOAD_DIR = os.getenv(
        "CLOSED_EYE_UPLOAD_DIR",
        os.path.join(BASE_DIR, "static", "uploads", "closed_eye"),
    )

    APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:5000")

    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS = _env_bool("MAIL_USE_TLS", default=True)
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_SENDER = os.getenv("MAIL_SENDER", MAIL_USERNAME or "no-reply@example.com")
    ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")

    FRAME_CAPTURE_INTERVAL_MS = int(os.getenv("FRAME_CAPTURE_INTERVAL_MS", "200"))
    LIVENESS_TIMEOUT_SECONDS = int(os.getenv("LIVENESS_TIMEOUT_SECONDS", "30"))

    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(4 * 1024 * 1024)))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", default=False)
    PERMANENT_SESSION_LIFETIME_MINUTES = int(
        os.getenv("PERMANENT_SESSION_LIFETIME_MINUTES", "20")
    )

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
