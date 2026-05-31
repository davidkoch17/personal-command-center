"""One-time OAuth flow for Whoop. Run once: python -m modules.integrations.whoop_auth

Opens a browser to authorize, captures the redirect on localhost:8501, exchanges
the code, and prints a refresh token to paste into ``.env`` as
``WHOOP_REFRESH_TOKEN``.
"""
import http.server
import os
import urllib.parse
import webbrowser

from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("WHOOP_CLIENT_ID")
CLIENT_SECRET = os.getenv("WHOOP_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8501"
AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
SCOPE = "read:recovery read:sleep read:profile read:cycles read:workout offline"


def run():
    if not (CLIENT_ID and CLIENT_SECRET):
        print("WHOOP_CLIENT_ID / WHOOP_CLIENT_SECRET missing in .env. Add them first.")
        return

    import httpx

    code_holder = {"code": None}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - http.server API
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            code_holder["code"] = params.get("code", [None])[0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>OK - you can close this window.</h1>")

        def log_message(self, *args):  # silence default stderr logging
            pass

    auth_url = (
        f"{AUTH_URL}?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}"
        f"&response_type=code&scope={urllib.parse.quote(SCOPE)}&state=x"
    )
    print(f"Opening: {auth_url}")
    webbrowser.open(auth_url)

    server = http.server.HTTPServer(("localhost", 8501), Handler)
    server.handle_request()

    if not code_holder["code"]:
        print("No code received.")
        return

    r = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code_holder["code"],
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
    )
    data = r.json()
    refresh = data.get("refresh_token")
    if refresh:
        print(f"\nRefresh token: {refresh}\nPaste into .env as WHOOP_REFRESH_TOKEN")
    else:
        print(f"\nNo refresh token in response: {data}")


if __name__ == "__main__":
    run()
