from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

from neuraec.adapters.base import Adapter
from neuraec.classifier import Classifier
from neuraec.nightly import apply_manual
from neuraec.records import EmailRecord, MailboxConfig


def _config_body(mailbox: MailboxConfig) -> dict:
    return {
        "N": mailbox.N,
        "order": mailbox.order,
        "provider": mailbox.provider,
        "labels": [
            {"rank": lab.rank, "provider_label": lab.provider_label, "text": lab.text}
            for lab in mailbox.labels
        ],
    }


def make_server(
    mailbox: MailboxConfig,
    adapter: Adapter | None,
    clf: Classifier,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> HTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            return

        def _send(self, code: int, payload: dict) -> None:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:
            path = urlparse(self.path).path.rstrip("/") or "/"
            if path in ("/config", "/neura/config"):
                self._send(200, _config_body(mailbox))
                return
            self._send(404, {"ok": False, "error": "not found"})

        def do_POST(self) -> None:
            path = urlparse(self.path).path.rstrip("/") or "/"
            if path not in ("/manual", "/neura/manual"):
                self._send(404, {"ok": False, "error": "not found"})
                return
            length = int(self.headers.get("Content-Length") or 0)
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send(400, {"ok": False, "error": "invalid json"})
                return
            if "rank" not in data:
                self._send(400, {"ok": False, "error": "manca rank"})
                return
            rec = EmailRecord(
                uid=str(data.get("uid") or ""),
                message_id=str(data.get("internetMessageId") or data.get("message_id") or ""),
            )
            try:
                apply_manual(mailbox, adapter, clf, rec, int(data["rank"]))
            except LookupError as exc:
                self._send(404, {"ok": False, "error": str(exc)})
                return
            except ValueError as exc:
                self._send(400, {"ok": False, "error": str(exc)})
                return
            except Exception as exc:
                self._send(500, {"ok": False, "error": str(exc)})
                return
            self._send(200, {"ok": True, "uid": rec.uid, "rank": int(data["rank"]), "user_action": "manual"})

    return HTTPServer((host, port), Handler)


def serve(
    mailbox: MailboxConfig,
    adapter: Adapter | None,
    clf: Classifier,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> None:
    httpd = make_server(mailbox, adapter, clf, host, port)
    print(f"neura serve su http://{host}:{port}")
    httpd.serve_forever()
