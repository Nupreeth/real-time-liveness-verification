import hmac
import csv
import io

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    Response,
    session,
    url_for,
)

from models.user import (
    get_recent_verification_events,
    get_user_by_email,
    get_user_by_email_and_token,
    log_verification_event,
    update_user_status,
)
from services.liveness_check import liveness_manager


camera_bp = Blueprint("camera", __name__)


@camera_bp.route("/camera")
def camera_page():
    email = session.get("verified_email")
    token = session.get("verified_token")

    if not email or not token:
        flash("Verify your email before accessing camera verification.", "error")
        return redirect(url_for("auth.register"))

    user = get_user_by_email_and_token(email, token)
    if not user:
        flash("Verification token is invalid or expired.", "error")
        return redirect(url_for("auth.register"))

    return render_template(
        "camera.html",
        email=email,
        token=token,
        frame_interval_ms=current_app.config["FRAME_CAPTURE_INTERVAL_MS"],
    )


@camera_bp.route("/process_frame", methods=["POST"])
def process_frame():
    payload = request.get_json(silent=True) or {}

    # Primary source is server session; payload is a fallback for environments
    # where session cookies are not persisted reliably.
    email = session.get("verified_email") or (payload.get("email") or "").strip().lower()
    token = session.get("verified_token") or (payload.get("token") or "").strip()
    if not email or not token:
        return (
            jsonify(
                {
                    "state": "failed",
                    "message": "Verification session expired. Please verify again.",
                }
            ),
            401,
        )

    user = get_user_by_email_and_token(email, token)
    if not user:
        return jsonify({"state": "failed", "message": "Invalid verification token."}), 403

    image_data = payload.get("image")
    if not image_data:
        return jsonify({"state": "pending", "message": "No frame provided."}), 400

    try:
        result = liveness_manager.process_frame(email=email, token=token, image_data=image_data)
    except Exception as exc:
        current_app.logger.exception("Frame processing failed unexpectedly: %s", exc)
        update_user_status(email, "FAILED")
        log_verification_event(
            email=email,
            status="FAILED",
            reason="internal_processing_error",
            open_captured=False,
            closed_captured=False,
        )
        session["result_email"] = email
        session.pop("verified_email", None)
        session.pop("verified_token", None)
        return jsonify({"state": "failed", "message": "Internal processing error."}), 500

    if result["state"] == "verified":
        update_user_status(email, "VERIFIED")
        log_verification_event(
            email=email,
            status="VERIFIED",
            reason=result.get("message", ""),
            open_captured=result.get("open_captured", False),
            closed_captured=result.get("closed_captured", False),
        )
        session["result_email"] = email
        session.pop("verified_email", None)
        session.pop("verified_token", None)
    elif result["state"] == "failed":
        update_user_status(email, "FAILED")
        log_verification_event(
            email=email,
            status="FAILED",
            reason=result.get("message", ""),
            open_captured=result.get("open_captured", False),
            closed_captured=result.get("closed_captured", False),
        )
        session["result_email"] = email
        session.pop("verified_email", None)
        session.pop("verified_token", None)

    return jsonify(result)


@camera_bp.route("/result")
def result_page():
    email = session.get("result_email")
    status = request.args.get("status", "").strip().upper()

    if email:
        user = get_user_by_email(email)
        if user:
            status = user["status"]

    if status not in {"VERIFIED", "FAILED", "PENDING"}:
        status = "FAILED"

    return render_template("result.html", status=status, email=email)


@camera_bp.route("/admin/events", methods=["GET"])
def admin_events():
    configured_key = current_app.config.get("ADMIN_API_KEY", "")
    if not configured_key:
        return jsonify({"error": "Admin API key is not configured."}), 403

    provided_key = (
        request.headers.get("X-Admin-Key", "").strip()
        or request.args.get("key", "").strip()
    )
    if not provided_key or not hmac.compare_digest(provided_key, configured_key):
        return jsonify({"error": "Unauthorized"}), 401

    limit = request.args.get("limit", "100")
    try:
        rows = get_recent_verification_events(limit=int(limit))
    except ValueError:
        rows = get_recent_verification_events(limit=100)

    return jsonify({"count": len(rows), "events": rows}), 200


@camera_bp.route("/admin/events.csv", methods=["GET"])
def admin_events_csv():
    configured_key = current_app.config.get("ADMIN_API_KEY", "")
    if not configured_key:
        return jsonify({"error": "Admin API key is not configured."}), 403

    provided_key = (
        request.headers.get("X-Admin-Key", "").strip()
        or request.args.get("key", "").strip()
    )
    if not provided_key or not hmac.compare_digest(provided_key, configured_key):
        return jsonify({"error": "Unauthorized"}), 401

    limit = request.args.get("limit", "500")
    try:
        rows = get_recent_verification_events(limit=int(limit))
    except ValueError:
        rows = get_recent_verification_events(limit=500)

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "id",
            "email",
            "status",
            "reason",
            "open_captured",
            "closed_captured",
            "created_at",
        ],
    )
    writer.writeheader()
    writer.writerows(rows)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=verification_events.csv"},
    )
