import smtplib
import socket
import json
import urllib.error
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app


def build_verification_url(token, base_url_override=None):
    base_url = (base_url_override or current_app.config["APP_BASE_URL"]).rstrip("/")
    return f"{base_url}/verify?token={token}"


def send_verification_email(recipient_email, token, base_url_override=None):
    verification_url = build_verification_url(token, base_url_override=base_url_override)

    username = current_app.config["MAIL_USERNAME"]
    password = current_app.config["MAIL_PASSWORD"]

    if not username or not password:
        current_app.logger.warning(
            "MAIL credentials missing. Use this verification link locally: %s",
            verification_url,
        )
        return False, verification_url, "MAIL credentials are not configured."

    message = MIMEMultipart("alternative")
    message["Subject"] = "Eye Verification - Email Confirmation"
    message["From"] = current_app.config["MAIL_SENDER"]
    message["To"] = recipient_email

    text_body = (
        "Please verify your email for the Eye Blink Verification System.\n"
        f"Verification link: {verification_url}\n"
        "If you did not request this, ignore this message."
    )
    html_body = f"""
    <p>Hello,</p>
    <p>Please verify your email for the Eye Blink Verification System.</p>
    <p><a href="{verification_url}">Click here to verify your email</a></p>
    <p>If you did not request this, ignore this message.</p>
    """
    message.attach(MIMEText(text_body, "plain"))
    message.attach(MIMEText(html_body, "html"))

    resend_api_key = current_app.config.get("RESEND_API_KEY", "")
    resend_error = ""
    if resend_api_key:
        from_email = current_app.config["MAIL_SENDER"] or current_app.config["MAIL_USERNAME"]
        payload = {
            "from": from_email,
            "to": [recipient_email],
            "subject": "Eye Verification - Email Confirmation",
            "text": text_body,
            "html": html_body,
        }
        request_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=request_data,
            method="POST",
            headers={
                "Authorization": f"Bearer {resend_api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                if response.status in (200, 201):
                    return True, verification_url, ""
                current_app.logger.warning("Resend returned non-success status: %s", response.status)
                resend_error = f"Resend HTTP status {response.status}"
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="ignore")
            current_app.logger.warning("Resend API rejected email: %s %s", exc.code, details)
            resend_error = f"Resend HTTPError {exc.code}: {details}"
        except urllib.error.URLError as exc:
            current_app.logger.warning("Resend network error: %s", exc)
            resend_error = f"Resend URLError: {exc}"

        # If Resend is configured but fails, continue to SMTP fallback.
        if resend_error:
            current_app.logger.warning("Resend attempt failed, falling back to SMTP: %s", resend_error)

    host = current_app.config["MAIL_SERVER"]
    sender = current_app.config["MAIL_SENDER"]
    primary_port = current_app.config["MAIL_PORT"]
    use_tls = current_app.config["MAIL_USE_TLS"]
    timeout_seconds = current_app.config["MAIL_TIMEOUT_SECONDS"]
    use_ssl_fallback = current_app.config["MAIL_USE_SSL_FALLBACK"]

    attempts = [(primary_port, use_tls, "primary")]
    if use_ssl_fallback and not (primary_port == 465 and not use_tls):
        attempts.append((465, False, "fallback_ssl_465"))

    errors = []
    if resend_error:
        errors.append(resend_error)
    for port, tls_enabled, label in attempts:
        try:
            if tls_enabled:
                with smtplib.SMTP(host, port, timeout=timeout_seconds) as smtp:
                    smtp.starttls()
                    smtp.login(username, password)
                    smtp.sendmail(sender, [recipient_email], message.as_string())
            else:
                with smtplib.SMTP_SSL(host, port, timeout=timeout_seconds) as smtp:
                    smtp.login(username, password)
                    smtp.sendmail(sender, [recipient_email], message.as_string())
            return True, verification_url, ""
        except (smtplib.SMTPException, socket.timeout, OSError) as exc:
            errors.append(f"{label}:{type(exc).__name__}:{exc}")
            current_app.logger.warning(
                "Email send attempt failed (%s on %s:%s): %s",
                label,
                host,
                port,
                exc,
            )

    current_app.logger.error("All email send attempts failed.")
    return False, verification_url, " | ".join(errors)
