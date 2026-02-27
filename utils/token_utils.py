import hmac
import secrets


def generate_verification_token():
    return secrets.token_urlsafe(32)


def safe_token_compare(token_a, token_b):
    if not token_a or not token_b:
        return False
    return hmac.compare_digest(token_a, token_b)
