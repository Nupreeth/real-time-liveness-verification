import re

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from models.user import (
    create_or_update_user,
    get_user_by_email,
    get_user_by_token,
)
from services.email_service import send_verification_email
from utils.token_utils import generate_verification_token


auth_bp = Blueprint("auth", __name__)
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _verification_base_url():
    # Supports LAN usage and reverse-proxy headers (ngrok/cloud).
    forwarded_proto = request.headers.get("X-Forwarded-Proto", "").strip()
    forwarded_host = request.headers.get("X-Forwarded-Host", "").strip()
    if forwarded_host:
        scheme = forwarded_proto or request.scheme or "http"
        return f"{scheme}://{forwarded_host}"
    return request.host_url.rstrip("/")


@auth_bp.route("/")
def root():
    return redirect(url_for("auth.register"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if len(email) > 254:
            flash("Email is too long.", "error")
            return render_template("register.html")

        if not EMAIL_REGEX.match(email):
            flash("Please enter a valid email address.", "error")
            return render_template("register.html")

        token = generate_verification_token()
        action = create_or_update_user(email, token)

        sent, _, error = send_verification_email(
            email,
            token,
            base_url_override=_verification_base_url(),
        )
        if sent:
            if action == "updated":
                flash(
                    "Email already registered. Fresh verification link sent. Open it from your inbox.",
                    "success",
                )
            else:
                flash(
                    "Verification email sent. Open the link from your inbox to continue.",
                    "success",
                )
            return redirect(url_for("auth.register"))

        flash(
            "Verification email could not be sent. Please verify mail settings and try again.",
            "error",
        )
        if error:
            current_app.logger.warning("Email send failed for %s: %s", email, error)
        return render_template("register.html")

    return render_template("register.html")


@auth_bp.route("/resend-verification", methods=["POST"])
def resend_verification():
    email = request.form.get("email", "").strip().lower()
    if not EMAIL_REGEX.match(email):
        flash("Invalid email for retry request.", "error")
        return redirect(url_for("auth.register"))

    existing_user = get_user_by_email(email)
    if not existing_user:
        flash("Email is not registered. Please register first.", "error")
        return redirect(url_for("auth.register"))

    token = generate_verification_token()
    create_or_update_user(email, token)

    sent, _, error = send_verification_email(
        email,
        token,
        base_url_override=_verification_base_url(),
    )
    if sent:
        flash("New verification email sent. Open the link from your inbox.", "success")
    else:
        flash(
            "Verification email could not be sent. Please verify mail settings and try again.",
            "error",
        )
        if error:
            current_app.logger.warning("Resend email failed for %s: %s", email, error)

    session["result_email"] = email
    return redirect(url_for("camera.result_page", status="PENDING"))


@auth_bp.route("/verify", methods=["GET", "POST"])
def verify():
    if request.method == "GET":
        token = request.args.get("token", "").strip()
    else:
        token = request.form.get("token", "").strip()

    token_user = get_user_by_token(token) if token else None

    if request.method == "POST":
        if not token_user:
            flash("Invalid or expired verification link.", "error")
            return render_template(
                "verify_email.html",
                token=token,
                token_valid=False,
            )

        session["verified_email"] = token_user["email"]
        session["verified_token"] = token
        session.permanent = True
        return redirect(url_for("camera.camera_page"))

    return render_template(
        "verify_email.html",
        token=token,
        token_valid=bool(token_user),
    )
