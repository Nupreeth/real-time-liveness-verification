import os
import sys

from sqlalchemy import create_engine, text


REQUIRED_ENV_VARS = [
    "DATABASE_URL",
    "APP_BASE_URL",
    "MAIL_USERNAME",
    "MAIL_PASSWORD",
    "MAIL_SENDER",
    "SECRET_KEY",
    "ADMIN_API_KEY",
]


def fail(message):
    print(f"[FAIL] {message}")
    return 1


def ok(message):
    print(f"[OK] {message}")


def main():
    missing = [key for key in REQUIRED_ENV_VARS if not os.getenv(key, "").strip()]
    if missing:
        print("[FAIL] Missing required environment variables:")
        for key in missing:
            print(f" - {key}")
        return 1

    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url.startswith(("postgresql://", "postgresql+psycopg2://")):
        return fail(
            "DATABASE_URL should be PostgreSQL for production, "
            "for example: postgresql+psycopg2://..."
        )
    ok("Required environment variables are present.")

    try:
        engine = create_engine(database_url, pool_pre_ping=True, future=True)
        with engine.connect() as conn:
            value = conn.execute(text("SELECT 1")).scalar()
            if value != 1:
                return fail("Database connection check returned unexpected result.")
        ok("Database connection successful (SELECT 1).")
    except Exception as exc:
        return fail(f"Database connection failed: {exc}")

    base_url = os.getenv("APP_BASE_URL", "")
    if not base_url.startswith("https://"):
        print(
            "[WARN] APP_BASE_URL is not HTTPS. Use HTTPS URL for hosted production deployment."
        )
    else:
        ok("APP_BASE_URL uses HTTPS.")

    ok("Pre-deploy checks completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
