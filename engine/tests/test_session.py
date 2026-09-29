"""The model process stays up and answers more than one command."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

CONFIG = {
    "mailbox_id": "mb-locale",
    "user_id": "me",
    "own_addresses": ["nome@dominio.it"],
    "N": 4,
    "order": "desc",
    "provider": "imap",
    "label_prefix": "N-P",
    "host": "imap.dominio.it",
    "username": "nome@dominio.it",
    "port": 993,
    "tls": "ssl",
    "profile": {"fig": [], "fun": [], "set": []},
    "labels": [
        {"rank": 0, "provider_label": "INBOX.N-P1", "text": "Priority 1"},
        {"rank": 1, "provider_label": "INBOX.N-P2", "text": "Priority 2"},
        {"rank": 2, "provider_label": "INBOX.N-P3", "text": "Priority 3"},
        {"rank": 3, "provider_label": "INBOX.N-P4", "text": "Priority 4"},
    ],
}


def _read_until(proc: subprocess.Popen[str], marker: str) -> list[str]:
    lines: list[str] = []
    assert proc.stdout is not None
    while True:
        line = proc.stdout.readline()
        if line == "":
            raise AssertionError(f"session closed before {marker}: {lines}")
        lines.append(line.rstrip("\n"))
        if marker in line:
            return lines


def test_session_answers_twice_without_restarting(tmp_path: Path) -> None:
    config = tmp_path / "mailbox.json"
    config.write_text(json.dumps(CONFIG), encoding="utf-8")
    data = tmp_path / "data"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "neuraec",
            "session",
            "--encoder",
            "fake",
            "--config",
            str(config),
            "--data",
            str(data),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        ready = _read_until(proc, '"ready"')
        assert any("@@NEURA" in line and '"ready": true' in line for line in ready)
        assert proc.stdin is not None
        for call_id in (1, 2):
            proc.stdin.write(
                json.dumps({"id": call_id, "cmd": "stats", "config": str(config), "data": str(data)}) + "\n"
            )
            proc.stdin.flush()
            done = _read_until(proc, f'"id": {call_id}')
            assert any(f'"code": 0' in line for line in done)
            assert any(line.startswith("open:") for line in done)
        proc.stdin.write(json.dumps({"id": 3, "cmd": "quit"}) + "\n")
        proc.stdin.flush()
        proc.wait(timeout=10)
        assert proc.returncode == 0
    finally:
        if proc.poll() is None:
            proc.kill()
