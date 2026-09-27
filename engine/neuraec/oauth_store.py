"""App OAuth clients and each mailbox's refresh token. Never inside mailbox.json."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class OAuthClients:
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    graph_client_id: str = ""
    graph_tenant: str = "common"

    def gmail_ready(self) -> bool:
        return bool(self.gmail_client_id.strip() and self.gmail_client_secret.strip())

    def graph_ready(self) -> bool:
        return bool(self.graph_client_id.strip())


def neura_home(config: Path | str) -> Path:
    """NEURA directory. If the mailbox lives in mailboxes/, this is the folder above it."""
    path = Path(config).expanduser().resolve()
    if path.parent.name == "mailboxes":
        return path.parent.parent
    return path.parent


def oauth_path(home: Path | str) -> Path:
    return Path(home) / "oauth.json"


def token_path(config: Path | str) -> Path:
    return Path(config).with_suffix(".token")


def load_oauth(home: Path | str) -> OAuthClients:
    path = oauth_path(home)
    if not path.is_file():
        return OAuthClients()
    data = json.loads(path.read_text(encoding="utf-8"))
    return OAuthClients(
        gmail_client_id=str(data.get("gmail_client_id") or ""),
        gmail_client_secret=str(data.get("gmail_client_secret") or ""),
        graph_client_id=str(data.get("graph_client_id") or ""),
        graph_tenant=str(data.get("graph_tenant") or "common").strip() or "common",
    )


def save_oauth(home: Path | str, clients: OAuthClients) -> None:
    path = oauth_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "gmail_client_id": clients.gmail_client_id.strip(),
        "gmail_client_secret": clients.gmail_client_secret.strip(),
        "graph_client_id": clients.graph_client_id.strip(),
        "graph_tenant": (clients.graph_tenant or "common").strip() or "common",
    }
    _write_private(path, json.dumps(payload, indent=2) + "\n")


def load_refresh(config: Path | str) -> str | None:
    path = token_path(config)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    token = str(data.get("refresh_token") or "").strip()
    return token or None


def load_token_email(config: Path | str) -> str:
    path = token_path(config)
    if not path.is_file():
        return ""
    data = json.loads(path.read_text(encoding="utf-8"))
    return str(data.get("email") or "").strip()


def has_refresh(config: Path | str) -> bool:
    return load_refresh(config) is not None


def save_refresh(config: Path | str, refresh_token: str, email: str) -> None:
    path = token_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"refresh_token": refresh_token.strip(), "email": email.strip()}
    _write_private(path, json.dumps(payload, indent=2) + "\n")


def _write_private(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
