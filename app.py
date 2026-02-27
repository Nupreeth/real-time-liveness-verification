import os
import logging
from datetime import timedelta
from pathlib import Path

from flask import Flask
from dotenv import load_dotenv

from config import Config
from models.user import init_db
from routes import init_app as init_routes


def _configure_logging(app):
    level_name = app.config.get("LOG_LEVEL", "INFO")
    level = getattr(logging, level_name, logging.INFO)
    app.logger.setLevel(level)

    if not app.logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
        )
        handler.setFormatter(formatter)
        app.logger.addHandler(handler)


def create_app():
    env_file = os.getenv("ENV_FILE", ".env")
    env_path = Path(env_file)
    if not env_path.is_absolute():
        env_path = Path(__file__).resolve().parent / env_path
    load_dotenv(env_path)

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    app.permanent_session_lifetime = timedelta(
        minutes=app.config["PERMANENT_SESSION_LIFETIME_MINUTES"]
    )

    _configure_logging(app)

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["OPEN_EYE_UPLOAD_DIR"], exist_ok=True)
    os.makedirs(app.config["CLOSED_EYE_UPLOAD_DIR"], exist_ok=True)

    with app.app_context():
        init_db()

    init_routes(app)

    @app.after_request
    def apply_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(self)"
        return response

    @app.errorhandler(413)
    def payload_too_large(_error):
        return {"state": "failed", "message": "Frame payload too large."}, 413

    @app.route("/health", methods=["GET"])
    def health():
        return {"status": "ok"}, 200

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=app.config["DEBUG"])
