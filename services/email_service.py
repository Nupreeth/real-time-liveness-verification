import smtplib
import socket
import json
import time
import base64
import urllib.error
import urllib.parse
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app


def build_verification_url(token, base_url_override=None):
    base_url = (base_url_override or current_app.config["APP_BASE_URL"]).rstrip("/")
    return f"{base_url}/verify?token={token}"


_gmail_access_token_cache = {"token": "", "expires_at": 0}


def _build_message(sender, recipient_email, verification_url):
    message = MIMEMultipart("alternative")
    message["Subject"] = "Eye Verification - Email Confirmation"
    message["From"] = sender
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
    return message, text_body, html_body


def _is_gmail_api_configured():
    return all(
        [
            current_app.config.get("GMAIL_API_CLIENT_ID"),
            current_app.config.get("GMAIL_API_CLIENT_SECRET"),
            current_app.config.get("GMAIL_API_REFRESH_TOKEN"),
        ]
    )


def _fetch_gmail_access_token():
    now = int(time.time())
    cached_token = _gmail_access_token_cache.get("token", "")
    expires_at = int(_gmail_access_token_cache.get("expires_at", 0))
    if cached_token and now < expires_at - 30:
        return cached_token

    data = urllib.parse.urlencode(
        {
            "client_id": current_app.config["GMAIL_API_CLIENT_ID"],
            "client_secret": current_app.config["GMAIL_API_CLIENT_SECRET"],
            "refresh_token": current_app.config["GMAIL_API_REFRESH_TOKEN"],
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))

    access_token = payload.get("access_token", "")
    expires_in = int(payload.get("expires_in", 3600))
    if not access_token:
        raise RuntimeError("Gmail API access token not returned.")

    _gmail_access_token_cache["token"] = access_token
    _gmail_access_token_cache["expires_at"] = now + expires_in
    return access_token


def _send_via_gmail_api(message):
    access_token = _fetch_gmail_access_token()
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    payload = json.dumps({"raw": raw_message}).encode("utf-8")
    req = urllib.request.Request(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        return response.status in (200, 202)


def send_verification_email(recipient_email, token, base_url_override=None):
    verification_url = build_verification_url(token, base_url_override=base_url_override)

    username = current_app.config["MAIL_USERNAME"]
    password = current_app.config["MAIL_PASSWORD"]
    resend_api_key = current_app.config.get("RESEND_API_KEY", "")
    sender = (
        current_app.config.get("GMAIL_API_SENDER")
        or username
        or current_app.config["MAIL_SENDER"]
        or "no-reply@example.com"
    )
    message, text_body, html_body = _build_message(sender, recipient_email, verification_url)

    provider_configured = _is_gmail_api_configured() or resend_api_key or (username and password)
    if not provider_configured:
        current_app.logger.warning(
            "No email provider credentials configured. Use this verification link locally: %s",
            verification_url,
        )
        return False, verification_url, "No email provider credentials are configured."

    errors = []
    if _is_gmail_api_configured():
        try:
            sent = _send_via_gmail_api(message)
            if sent:
                return True, verification_url, ""
            errors.append("Gmail API returned non-success status.")
        except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError, ValueError) as exc:
            errors.append(f"GmailAPI:{type(exc).__name__}:{exc}")
            current_app.logger.warning("Gmail API send failed: %s", exc)

    resend_error = ""
    if resend_api_key:
        from_email = (
            current_app.config.get("RESEND_FROM_EMAIL")
            or sender
        )
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
                "User-Agent": current_app.config.get(
                    "RESEND_USER_AGENT",
                    "eye-verification-system/1.0",
                ),
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
            errors.append(resend_error)

    host = current_app.config["MAIL_SERVER"]
    primary_port = current_app.config["MAIL_PORT"]
    use_tls = current_app.config["MAIL_USE_TLS"]
    timeout_seconds = current_app.config["MAIL_TIMEOUT_SECONDS"]
    use_ssl_fallback = current_app.config["MAIL_USE_SSL_FALLBACK"]

    attempts = []
    if username and password:
        attempts.append((primary_port, use_tls, "primary"))
        if use_ssl_fallback and not (primary_port == 465 and not use_tls):
            attempts.append((465, False, "fallback_ssl_465"))
    elif not _is_gmail_api_configured() and not resend_api_key:
        errors.append("SMTP credentials are not configured.")
        current_app.logger.error("All email send attempts failed.")
        return False, verification_url, " | ".join(errors)

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
    if not attempts and errors:
        return False, verification_url, " | ".join(errors)
    return False, verification_url, " | ".join(errors)
