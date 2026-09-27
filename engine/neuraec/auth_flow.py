"""Login nel browser, di ritorno su 127.0.0.1. Nessun server pubblico."""

from __future__ import annotations

import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable
from urllib.parse import parse_qs, urlparse

GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.modify"
AUTH_PORT = 8766
GRAPH_REDIRECT = f"http://127.0.0.1:{AUTH_PORT}"


def gmail_login(client_id: str, client_secret: str, say: Callable[[str], None]) -> tuple[str, str]:
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise SystemExit(
            "manca google-auth-oauthlib (pip install google-api-python-client google-auth google-auth-oauthlib)"
        ) from exc

    say("waiting for the browser…")
    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        },
        scopes=[GMAIL_SCOPE],
    )
    creds = flow.run_local_server(port=0, open_browser=True, prompt="consent", authorization_prompt_message="")
    refresh = getattr(creds, "refresh_token", None) or ""
    if not refresh:
        raise SystemExit("Google did not return a refresh token: connect again")
    email = ""
    try:
        service = build("gmail", "v1", credentials=Credentials(
            token=creds.token,
            refresh_token=refresh,
            client_id=client_id,
            client_secret=client_secret,
            token_uri="https://oauth2.googleapis.com/token",
        ), cache_discovery=False)
        profile = service.users().getProfile(userId="me").execute()
        email = str(profile.get("emailAddress") or "")
    except Exception:
        email = ""
    return refresh, email


def graph_login(client_id: str, tenant: str, say: Callable[[str], None]) -> tuple[str, str]:
    try:
        import msal
        import requests
    except ImportError as exc:
        raise SystemExit("manca msal (pip install msal requests)") from exc

    from neuraec.adapters.graph import GRAPH_DELEGATED_SCOPES

    app = msal.PublicClientApplication(
        client_id,
        authority=f"https://login.microsoftonline.com/{tenant or 'common'}",
    )
    flow = app.initiate_auth_code_flow(list(GRAPH_DELEGATED_SCOPES), redirect_uri=GRAPH_REDIRECT)
    if "error" in flow:
        raise SystemExit(flow.get("error_description") or flow.get("error") or "avvio login Microsoft fallito")
    say("waiting for the browser…")
    webbrowser.open(flow["auth_uri"])
    query = _capture_redirect(AUTH_PORT)
    result = app.acquire_token_by_auth_code_flow(flow, query)
    if "refresh_token" not in result:
        raise SystemExit(result.get("error_description") or result.get("error") or "Microsoft token was not obtained")
    email = ""
    access = result.get("access_token") or ""
    if access:
        try:
            resp = requests.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {access}"},
                params={"$select": "mail,userPrincipalName"},
                timeout=30,
            )
            if resp.ok:
                body = resp.json()
                email = str(body.get("mail") or body.get("userPrincipalName") or "")
        except Exception:
            email = ""
    return str(result["refresh_token"]), email


def _capture_redirect(port: int) -> dict[str, str]:
    box: dict[str, str] = {}
    done = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            for key, values in parse_qs(parsed.query).items():
                if values:
                    box[key] = values[0]
            body = (
                "<html><body><p>Collegamento ricevuto. Puoi chiudere questa finestra "
                "e tornare a NEURA.</p></body></html>"
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            done.set()

        def log_message(self, fmt: str, *args) -> None:
            return

    server = HTTPServer(("127.0.0.1", port), Handler)
    server.timeout = 180
    while not done.is_set():
        server.handle_request()
    server.server_close()
    if not box:
        raise SystemExit("nessuna risposta dal browser")
    return box
