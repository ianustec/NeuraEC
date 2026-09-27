from __future__ import annotations

import json
from pathlib import Path

from neuraec.cli import main
from neuraec.oauth_store import OAuthClients, has_refresh, load_oauth, load_refresh, save_oauth, save_refresh


def _mailbox(path: Path, provider: str) -> None:
    path.write_text(
        json.dumps(
            {
                "mailbox_id": "mb-cloud",
                "user_id": "cloud",
                "own_addresses": ["a@b.it"],
                "N": 3,
                "order": "desc",
                "provider": provider,
                "host": "",
                "username": "a@b.it",
            }
        ),
        encoding="utf-8",
    )


def test_token_is_not_inside_mailbox_json(tmp_path: Path):
    config = tmp_path / "mailbox.json"
    _mailbox(config, "gmail")
    save_oauth(
        tmp_path,
        OAuthClients(gmail_client_id="id", gmail_client_secret="secret", graph_client_id="gid"),
    )
    save_refresh(config, "refresh-segreto", "a@b.it")
    text = config.read_text(encoding="utf-8")
    assert "refresh-segreto" not in text
    assert "secret" not in text
    assert has_refresh(config)
    assert load_refresh(config) == "refresh-segreto"
    clients = load_oauth(tmp_path)
    assert clients.gmail_ready()
    assert clients.graph_ready()
    assert oct((tmp_path / "oauth.json").stat().st_mode & 0o777) == oct(0o600)


def test_cycle_skips_gmail_without_token(tmp_path: Path, monkeypatch, capsys):
    config = tmp_path / "mailbox.json"
    _mailbox(config, "gmail")
    opened: list[str] = []

    def boom(*_args, **_kwargs):
        opened.append("yes")
        raise AssertionError("must not open Gmail without a token")

    monkeypatch.setattr("neuraec.cli._open_adapter", boom)
    code = main(["cycle", "--config", str(config), "--data", str(tmp_path / "data"), "--encoder", "fake"])
    out = capsys.readouterr().out
    assert code == 1
    assert opened == []
    assert "not connected" in out
