import smtplib
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

    try:
        with smtplib.SMTP(
            current_app.config["MAIL_SERVER"],
            current_app.config["MAIL_PORT"],
            timeout=20,
        ) as smtp:
            if current_app.config["MAIL_USE_TLS"]:
                smtp.starttls()
            smtp.login(username, password)
            smtp.sendmail(
                current_app.config["MAIL_SENDER"],
                [recipient_email],
                message.as_string(),
            )
        return True, verification_url, ""
    except smtplib.SMTPException as exc:
        current_app.logger.exception("SMTP failure while sending verification email.")
        return False, verification_url, str(exc)
    except Exception as exc:
        current_app.logger.exception("Unexpected failure while sending verification email.")
        return False, verification_url, str(exc)
