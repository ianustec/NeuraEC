from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

from neuraec.bench.prequential import DEFAULT_CSV, format_report, run_prequential
from neuraec.classifier import Classifier
from neuraec.config import load_mailbox_config
from neuraec.encoder import FakeEncoder, try_sentence_encoder
from neuraec.registry import Registry
from neuraec.state import UserState


def resolve_encoder(choice: str):
    if choice == "fake":
        return FakeEncoder()
    if choice == "minilm":
        encoder = try_sentence_encoder()
        if encoder is None:
            print("warning: sentence-transformers is not installed; using FakeEncoder", file=sys.stderr)
            return FakeEncoder()
        return encoder
    encoder = try_sentence_encoder()
    if encoder is None:
        print("warning: MiniLM is not available; using FakeEncoder", file=sys.stderr)
        return FakeEncoder()
    return encoder


def _add_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=Path, default=Path("mailbox.json"))
    parser.add_argument("--data", type=Path, default=Path(".neura-work"))
    parser.add_argument("--encoder", choices=("auto", "minilm", "fake"), default="auto")
    parser.add_argument("--adapter", choices=("imap", "gmail", "graph", "fake"), default=None)


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"set {name} (secrets do not belong in mailbox.json)")
    return value


def _open_adapter(mailbox, kind: str | None, *, password: str | None = None, config_path: Path | None = None):
    kind = kind or getattr(mailbox, "provider", None) or "imap"
    if kind == "fake":
        from neuraec.adapters.fake import FakeAdapter

        return FakeAdapter()
    if kind == "gmail":
        from neuraec.adapters.gmail import GmailAdapter
        from neuraec.oauth_store import load_oauth, load_refresh, neura_home

        if config_path is None:
            raise SystemExit("missing the mailbox file for the Gmail token")
        clients = load_oauth(neura_home(config_path))
        refresh = load_refresh(config_path) or os.environ.get("NEURA_GMAIL_REFRESH_TOKEN", "").strip()
        client_id = clients.gmail_client_id or os.environ.get("NEURA_GMAIL_CLIENT_ID", "").strip()
        client_secret = clients.gmail_client_secret or os.environ.get("NEURA_GMAIL_CLIENT_SECRET", "").strip()
        if not client_id or not client_secret:
            raise SystemExit("missing the Gmail client in oauth.json")
        if not refresh:
            raise SystemExit("Gmail is not connected")
        return GmailAdapter(
            client_id,
            client_secret,
            refresh,
            label_prefix=mailbox.label_prefix,
            placement=mailbox.placement,
        )
    if kind == "graph":
        from neuraec.adapters.graph import GraphAdapter
        from neuraec.oauth_store import load_oauth, load_refresh, neura_home

        if config_path is None:
            raise SystemExit("missing the mailbox file for the Microsoft token")
        clients = load_oauth(neura_home(config_path))
        refresh = load_refresh(config_path) or os.environ.get("NEURA_GRAPH_REFRESH_TOKEN", "").strip()
        client_id = clients.graph_client_id or os.environ.get("NEURA_GRAPH_CLIENT_ID", "").strip()
        tenant = clients.graph_tenant or os.environ.get("NEURA_GRAPH_TENANT", "common").strip() or "common"
        if not client_id:
            raise SystemExit("missing the Microsoft client in oauth.json")
        if not refresh:
            raise SystemExit("Microsoft is not connected")
        return GraphAdapter(
            client_id,
            "",
            refresh,
            tenant=tenant,
            label_prefix=mailbox.label_prefix,
            placement=mailbox.placement,
        )
    if password is None:
        password = os.environ.get("NEURA_IMAP_PASSWORD")
    if not password:
        raise SystemExit("set NEURA_IMAP_PASSWORD (the password does not belong in mailbox.json)")
    if not mailbox.host:
        raise SystemExit("mailbox.json: missing host")
    from neuraec.adapters.imap import ImapAdapter

    return ImapAdapter(
        mailbox.host,
        mailbox.username,
        password,
        port=mailbox.port,
        tls=mailbox.tls,
    )


def _runtime(args, *, with_adapter: bool = True):
    mailbox = load_mailbox_config(args.config)
    encoder = resolve_encoder(args.encoder)
    user_root = Path(args.data) / "users" / mailbox.user_id
    box_root = Path(args.data) / "mailboxes" / mailbox.mailbox_id
    state = UserState(
        user_root,
        user_id=mailbox.user_id,
        N=mailbox.N,
        order=mailbox.order,
        profile=mailbox.profile,
        encoder_name=encoder.name,
    )
    registry = Registry(box_root / "pred.sqlite")
    from neuraec.prior_net import default_prior_path, load_accepted

    clf = Classifier(mailbox, state, encoder, registry, prior_net=load_accepted(default_prior_path()))
    adapter = _open_adapter(mailbox, args.adapter, config_path=Path(args.config)) if with_adapter else None
    return mailbox, adapter, clf


def _print_stats(stats: dict) -> None:
    print(f"open: {stats['n_open']}")
    print(f"corrections: {stats['n_corr']}")
    print(f"confirmations: {stats['n_conf']}")
    print(f"replies: {stats['n_replied']}")
    print(f"labeled: {stats['n_labeled']}")
    print(f"corrections/100: {stats['corrections_per_100']}")
    print(f"accuracy: {stats['accuracy']}")
    print(f"mae: {stats['mae']}")
    print(f"expired: {stats.get('n_expired', 0)}")
    for name in ("thread", "sender", "domain", "memory", "prior"):
        print(f"stage {name}: {(stats.get('stages') or {}).get(name, 0)}")
    for rank, count in sorted((stats.get("ranks") or {}).items()):
        print(f"rank {rank}: {count}")
    for rec in stats.get("recent") or []:
        conf = rec.get("pred_conf") or 0
        print(
            f"recent\t{rec.get('from_addr') or ''}\t{rec.get('pred_rank')}\t"
            f"{rec.get('stage') or ''}\t{conf}\t{rec.get('written_label') or ''}"
        )


def _say(message: str) -> None:
    print(message, flush=True)


def _open_or_reject(args):
    """Open the mailbox. Prints login ok or login rejected."""
    _say("connecting to the mailbox…")
    mailbox, adapter, clf = _runtime(args)
    try:
        adapter.connect()
    except Exception as exc:
        _say(f"login rejected: {exc}")
        adapter.close()
        return None
    _say("login ok")
    return mailbox, adapter, clf


def cmd_check(args) -> int:
    opened = _open_or_reject(args)
    if opened is None:
        return 1
    mailbox, adapter, _clf = opened
    try:
        labels = adapter.supports_labels()
    finally:
        adapter.close()
    _say(f"labels: {'yes' if labels else 'no'}")
    _say(f"placement: {'label, stays in the inbox' if mailbox.placement == 'label' else 'move into the folder'}")
    return 0


def cmd_init(args) -> int:
    from neuraec.nightly import init_mailbox

    opened = _open_or_reject(args)
    if opened is None:
        return 1
    mailbox, adapter, clf = opened
    try:
        info = init_mailbox(mailbox, adapter, clf, progress=_say)
    except Exception as exc:
        _say(f"error: {exc}")
        return 1
    finally:
        adapter.close()
    _say(f"folders: {len(mailbox.labels)}")
    _say(f"sent messages read: {info['n_sent']}")
    _say(f"recipients in replied_to: {info['n_replied_keys']}")
    return 0


def cmd_predict(args) -> int:
    from neuraec.nightly import observe_moves, predict_unseen, write_notify_queue

    mailbox, adapter, clf = _runtime(args)
    with adapter:
        out = predict_unseen(mailbox, adapter, clf)
        moves = observe_moves(mailbox, adapter, clf)
    write_notify_queue(mailbox, out, args.data)
    print(f"labeled: {len(out)}")
    for rec, pred in out:
        print(f"  {rec.uid} → {mailbox.label_for_rank(pred.rank)} rank={pred.rank} stage={pred.stage}")
    if moves.kpi.get("error"):
        print(f"could not read moves: {moves.kpi['error']}", file=sys.stderr)
    elif moves.n_observed:
        print(f"learned {moves.n_corr} corrections and {moves.n_replied} replies from your moves")
    return 0


def cmd_nightly(args) -> int:
    from neuraec.nightly import nightly

    mailbox, adapter, clf = _runtime(args)
    with adapter:
        report = nightly(mailbox, adapter, clf)
    if report.kpi.get("error"):
        print(f"provider error: {report.kpi['error']}", file=sys.stderr)
        return 1
    print(
        f"osservate={report.n_observed} corr={report.n_corr} conf={report.n_conf} "
        f"replied={report.n_replied} deleted={report.n_deleted} unread={report.n_unread} "
        f"expired={report.n_expired}"
    )
    _print_stats(report.kpi)
    return 0


def cmd_prior_train(args) -> int:
    from neuraec.prior_net import default_prior_path
    from neuraec.prior_train import format_train_report, run_prior_train

    if args.encoder == "minilm":
        encoder = try_sentence_encoder()
        if encoder is None:
            print("warning: sentence-transformers is not installed; using FakeEncoder", file=sys.stderr)
            encoder = FakeEncoder()
    else:
        encoder = FakeEncoder()
    out = args.out or default_prior_path()
    report = run_prior_train(encoder, data_root=args.data, csv_path=args.csv, out=out)
    print(format_train_report(report))
    print(f"weights: {out}")
    return 0


def cmd_auth(args) -> int:
    from neuraec.auth_flow import gmail_login, graph_login
    from neuraec.oauth_store import load_oauth, neura_home, save_refresh

    config = Path(args.config)
    if not config.is_file():
        raise SystemExit(f"missing {config}")
    clients = load_oauth(neura_home(config))
    if args.provider == "gmail":
        if not clients.gmail_ready():
            raise SystemExit("missing the Gmail client in oauth.json")
        refresh, email = gmail_login(clients.gmail_client_id, clients.gmail_client_secret, _say)
    else:
        if not clients.graph_ready():
            raise SystemExit("missing the Microsoft client in oauth.json")
        refresh, email = graph_login(clients.graph_client_id, clients.graph_tenant, _say)
    save_refresh(config, refresh, email)
    _say(f"connected: {email or 'account'}")
    return 0


def cmd_cycle(args) -> int:
    from neuraec.cycle import CycleMailbox, imap_password, mailbox_paths, run_cycle

    primary = Path(args.config)
    boxes: list[CycleMailbox] = []
    primary_missing = False
    primary_id = None
    for path in mailbox_paths(primary):
        mailbox = load_mailbox_config(path)
        if path.resolve() == primary.resolve():
            primary_id = mailbox.mailbox_id
        kind = args.adapter or mailbox.provider
        secret = None
        if kind == "imap":
            secret = imap_password(path, primary)
            if not secret:
                _say(f"skip {mailbox.mailbox_id}: password missing")
                if path.resolve() == primary.resolve():
                    primary_missing = True
                continue
        elif kind in ("gmail", "graph"):
            from neuraec.oauth_store import has_refresh

            if not has_refresh(path):
                _say(f"skip {mailbox.mailbox_id}: not connected")
                if path.resolve() == primary.resolve():
                    primary_missing = True
                continue
        try:
            adapter = _open_adapter(mailbox, kind, password=secret, config_path=path)
        except SystemExit as exc:
            _say(f"skip {mailbox.mailbox_id}: {exc}")
            if path.resolve() == primary.resolve():
                return 1
            continue
        boxes.append(CycleMailbox(mailbox, adapter))
    if primary_missing:
        return 1
    if not boxes:
        _say("no mailboxes")
        return 1
    encoder = resolve_encoder(args.encoder)
    results = run_cycle(boxes, encoder, args.data, progress=_say)
    if primary_id is not None and any(row.get("error") and row["mailbox_id"] == primary_id for row in results):
        return 1
    return 0


def cmd_stats(args) -> int:
    from neuraec.nightly import compute_stats

    _mailbox, _adapter, clf = _runtime(args, with_adapter=False)
    _print_stats(compute_stats(clf.registry))
    return 0


def cmd_manual(args) -> int:
    from neuraec.nightly import apply_manual
    from neuraec.records import EmailRecord

    if not args.uid and not args.message_id:
        raise SystemExit("neura manual richiede --uid oppure --message-id")
    mailbox, adapter, clf = _runtime(args)
    rec = EmailRecord(uid=args.uid or "", message_id=args.message_id or "")
    with adapter:
        apply_manual(mailbox, adapter, clf, rec, args.rank)
    print(f"manual uid={rec.uid} rank={args.rank} → {mailbox.label_for_rank(args.rank)}")
    return 0


def cmd_serve(args) -> int:
    from neuraec.serve import serve

    mailbox, adapter, clf = _runtime(args)
    with adapter:
        serve(mailbox, adapter, clf, host=args.host, port=args.port)
    return 0


def cmd_encoder() -> int:
    """Carica l'encoder una volta e stampa nome, origine dei pesi e tempo."""
    import time

    from neuraec.encoder import local_model_dir

    started = time.monotonic()
    encoder = resolve_encoder("auto")
    local = local_model_dir(encoder.name)
    vec = encoder.encode("model load check")
    elapsed = time.monotonic() - started
    source = str(local) if local is not None else ("bundled" if encoder.name.startswith("fake") else "cache")
    print(f"encoder\t{encoder.name}\t{vec.shape[0]}\t{source}\t{elapsed:.1f}s")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="neuraec")
    sub = parser.add_subparsers(dest="cmd", required=True)

    bench = sub.add_parser("bench", help="prequential benchmark on the historical CSV")
    bench.add_argument("--encoder", choices=("fake", "minilm"), default="fake")
    bench.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    bench.add_argument("--workdir", type=Path, default=None)

    sub.add_parser("crosslingual", help="§10.5 test when MiniLM and Opus-MT are available")

    for name, help_text in (
        ("check", "check host, username and password"),
        ("init", "create priority folders and read Sent"),
        ("predict", "classify unread mail and write the label"),
        ("nightly", "observe open rows and call observe"),
        ("cycle", "classify every mailbox with one encoder; observe at night"),
        ("stats", "open, corrections, confirmations, corrections/100"),
    ):
        p = sub.add_parser(name, help=help_text)
        _add_runtime_args(p)

    manual = sub.add_parser("manual", help="immediate manual observation (add-in / UI)")
    _add_runtime_args(manual)
    manual.add_argument("--rank", type=int, required=True)
    manual.add_argument("--uid", default="")
    manual.add_argument("--message-id", default="")

    serve = sub.add_parser("serve", help="local HTTP server for the Outlook add-in")
    _add_runtime_args(serve)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)

    auth = sub.add_parser("auth", help="connect Gmail or Microsoft in the browser")
    auth.add_argument("provider", choices=("gmail", "graph"))
    auth.add_argument("--config", type=Path, required=True)

    sub.add_parser("encoder", help="load the model and report whether weights come from the app or the cache")

    prior = sub.add_parser("prior-train", help="train prior v1 offline and accept it only if it beats v0")
    prior.add_argument("--data", type=Path, default=Path(".neura-work"))
    prior.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    prior.add_argument("--encoder", choices=("fake", "minilm"), default="fake")
    prior.add_argument("--out", type=Path, default=None)

    args = parser.parse_args(argv)
    if args.cmd == "crosslingual":
        from neuraec.bench.crosslingual import main as xl_main

        return xl_main()

    if args.cmd == "bench":
        if args.encoder == "minilm":
            encoder = try_sentence_encoder()
            if encoder is None:
                print("sentence-transformers is not installed; using FakeEncoder")
                encoder = FakeEncoder()
        else:
            encoder = FakeEncoder()
        workdir = args.workdir or Path(tempfile.mkdtemp(prefix="neura-bench-"))
        result = run_prequential(encoder=encoder, csv_path=args.csv, workdir=workdir, persist=False)
        print(format_report(result))
        return 0

    if args.cmd == "encoder":
        return cmd_encoder()
    if args.cmd == "check":
        return cmd_check(args)
    if args.cmd == "init":
        return cmd_init(args)
    if args.cmd == "predict":
        return cmd_predict(args)
    if args.cmd == "nightly":
        return cmd_nightly(args)
    if args.cmd == "cycle":
        return cmd_cycle(args)
    if args.cmd == "auth":
        return cmd_auth(args)
    if args.cmd == "stats":
        return cmd_stats(args)
    if args.cmd == "manual":
        return cmd_manual(args)
    if args.cmd == "serve":
        return cmd_serve(args)
    if args.cmd == "prior-train":
        return cmd_prior_train(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
