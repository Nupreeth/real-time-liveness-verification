from datetime import datetime, timezone

from flask import current_app
from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    desc,
    select,
    text,
    update,
)
from sqlalchemy.engine import Engine


VALID_STATUSES = {"PENDING", "VERIFIED", "FAILED"}

_ENGINE_CACHE = {}
_METADATA = MetaData()

_USERS_TABLE = Table(
    "users",
    _METADATA,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("email", String(255), nullable=False, unique=True),
    Column("verification_token", String(512)),
    Column("status", String(20), nullable=False, server_default=text("'PENDING'")),
)

_VERIFICATION_EVENTS_TABLE = Table(
    "verification_events",
    _METADATA,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("email", String(255), nullable=False),
    Column("status", String(20), nullable=False),
    Column("reason", String(500), nullable=False, server_default=text("''")),
    Column("open_captured", Integer, nullable=False, server_default=text("0")),
    Column("closed_captured", Integer, nullable=False, server_default=text("0")),
    Column("created_at", String(64), nullable=False),
)


def _normalize_database_url(database_url):
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql://", 1)
    return database_url


def get_engine():
    database_url = (current_app.config.get("DATABASE_URL") or "").strip()
    if not database_url:
        database_path = current_app.config["DATABASE_PATH"]
        database_url = f"sqlite:///{database_path}"

    database_url = _normalize_database_url(database_url)

    engine = _ENGINE_CACHE.get(database_url)
    if engine:
        return engine

    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(
        database_url,
        future=True,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
    _ENGINE_CACHE[database_url] = engine
    return engine


def _row_to_dict(row):
    return dict(row._mapping) if row else None


def init_db():
    engine: Engine = get_engine()
    _METADATA.create_all(engine)


def create_or_update_user(email, token):
    engine = get_engine()
    with engine.begin() as connection:
        existing = connection.execute(
            select(_USERS_TABLE.c.id).where(_USERS_TABLE.c.email == email)
        ).first()

        if existing:
            connection.execute(
                update(_USERS_TABLE)
                .where(_USERS_TABLE.c.email == email)
                .values(verification_token=token, status="PENDING")
            )
            return "updated"

        connection.execute(
            _USERS_TABLE.insert().values(
                email=email,
                verification_token=token,
                status="PENDING",
            )
        )
        return "created"


def get_user_by_email(email):
    engine = get_engine()
    with engine.begin() as connection:
        row = connection.execute(
            select(
                _USERS_TABLE.c.id,
                _USERS_TABLE.c.email,
                _USERS_TABLE.c.verification_token,
                _USERS_TABLE.c.status,
            ).where(_USERS_TABLE.c.email == email)
        ).first()
    return _row_to_dict(row)


def get_user_by_token(token):
    engine = get_engine()
    with engine.begin() as connection:
        row = connection.execute(
            select(
                _USERS_TABLE.c.id,
                _USERS_TABLE.c.email,
                _USERS_TABLE.c.verification_token,
                _USERS_TABLE.c.status,
            ).where(_USERS_TABLE.c.verification_token == token)
        ).first()
    return _row_to_dict(row)


def get_user_by_email_and_token(email, token):
    engine = get_engine()
    with engine.begin() as connection:
        row = connection.execute(
            select(
                _USERS_TABLE.c.id,
                _USERS_TABLE.c.email,
                _USERS_TABLE.c.verification_token,
                _USERS_TABLE.c.status,
            ).where(
                (_USERS_TABLE.c.email == email)
                & (_USERS_TABLE.c.verification_token == token)
            )
        ).first()
    return _row_to_dict(row)


def update_user_status(email, status):
    normalized_status = status.upper()
    if normalized_status not in VALID_STATUSES:
        raise ValueError(f"Invalid user status: {status}")

    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(
            update(_USERS_TABLE)
            .where(_USERS_TABLE.c.email == email)
            .values(status=normalized_status)
        )


def log_verification_event(email, status, reason="", open_captured=False, closed_captured=False):
    normalized_status = status.upper()
    if normalized_status not in VALID_STATUSES:
        raise ValueError(f"Invalid user status for event log: {status}")

    created_at = datetime.now(timezone.utc).isoformat()
    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(
            _VERIFICATION_EVENTS_TABLE.insert().values(
                email=email,
                status=normalized_status,
                reason=reason or "",
                open_captured=int(bool(open_captured)),
                closed_captured=int(bool(closed_captured)),
                created_at=created_at,
            )
        )


def get_recent_verification_events(limit=100):
    safe_limit = max(1, min(int(limit), 500))
    engine = get_engine()
    with engine.begin() as connection:
        rows = connection.execute(
            select(
                _VERIFICATION_EVENTS_TABLE.c.id,
                _VERIFICATION_EVENTS_TABLE.c.email,
                _VERIFICATION_EVENTS_TABLE.c.status,
                _VERIFICATION_EVENTS_TABLE.c.reason,
                _VERIFICATION_EVENTS_TABLE.c.open_captured,
                _VERIFICATION_EVENTS_TABLE.c.closed_captured,
                _VERIFICATION_EVENTS_TABLE.c.created_at,
            )
            .order_by(desc(_VERIFICATION_EVENTS_TABLE.c.id))
            .limit(safe_limit)
        ).fetchall()
    return [dict(row._mapping) for row in rows]
