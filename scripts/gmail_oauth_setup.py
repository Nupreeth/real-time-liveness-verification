import argparse
import json
import threading
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from dotenv import load_dotenv


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.send"


def load_env(env_file):
    env_path = Path(env_file)
    if not env_path.is_absolute():
        env_path = Path(__file__).resolve().parents[1] / env_path
    load_dotenv(env_path)
    return env_path


def require_env(name):
    import os

    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required env var: {name}")
    return value


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    server_version = "EyeVerificationOAuth/1.0"

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        self.server.auth_code = query.get("code", [""])[0]
        self.server.auth_error = query.get("error", [""])[0]

        if self.server.auth_code:
            body = (
                "<html><body><h1>Authorization complete</h1>"
                "<p>You can close this window and return to the terminal.</p>"
                "</body></html>"
            )
            self.send_response(200)
        else:
            body = (
                "<html><body><h1>Authorization failed</h1>"
                "<p>Return to the terminal to inspect the error.</p>"
                "</body></html>"
            )
            self.send_response(400)

        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body.encode("utf-8"))))
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, _format, *_args):
        return


def build_auth_url(client_id, redirect_uri):
    query = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "access_type": "offline",
            "prompt": "consent",
            "scope": GMAIL_SCOPE,
        }
    )
    return f"{GOOGLE_AUTH_URL}?{query}"


def exchange_code(client_id, client_secret, redirect_uri, code):
    payload = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        GOOGLE_TOKEN_URL,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    parser = argparse.ArgumentParser(
        description="Generate a Gmail API refresh token for hosted email delivery."
    )
    parser.add_argument("--env-file", default=".env", help="Env file to load.")
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Local callback port for OAuth redirect.",
    )
    args = parser.parse_args()

    load_env(args.env_file)
    client_id = require_env("GMAIL_API_CLIENT_ID")
    client_secret = require_env("GMAIL_API_CLIENT_SECRET")
    redirect_uri = f"http://127.0.0.1:{args.port}/oauth2callback"

    server = HTTPServer(("127.0.0.1", args.port), OAuthCallbackHandler)
    server.auth_code = ""
    server.auth_error = ""

    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()

    print("Open this URL in your browser and complete Google sign-in:")
    print()
    print(build_auth_url(client_id, redirect_uri))
    print()
    print("Waiting for Google callback on", redirect_uri)

    thread.join()
    server.server_close()

    if server.auth_error:
        raise SystemExit(f"Google OAuth returned error: {server.auth_error}")
    if not server.auth_code:
        raise SystemExit("No authorization code received.")

    token_data = exchange_code(client_id, client_secret, redirect_uri, server.auth_code)
    refresh_token = token_data.get("refresh_token", "")
    if not refresh_token:
        raise SystemExit(
            "No refresh token returned. Re-run and ensure the OAuth consent screen shows a consent prompt."
        )

    print()
    print("Add this secret to your local/prod env:")
    print(f"GMAIL_API_REFRESH_TOKEN={refresh_token}")


if __name__ == "__main__":
    main()
