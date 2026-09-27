"""One process, one encoder, one mailbox at a time."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from neuraec.adapters.base import Adapter
from neuraec.classifier import Classifier
from neuraec.config import load_mailbox_config
from neuraec.encoder import Encoder
from neuraec.records import MailboxConfig, utcnow
from neuraec.registry import Registry
from neuraec.state import UserState, user_dir_lock


@dataclass
class CycleMailbox:
    mailbox: MailboxConfig
    adapter: Adapter


def mailbox_paths(primary: Path) -> list[Path]:
    """The primary mailbox, then ~/.neura/mailboxes/*.json when present."""
    primary = Path(primary)
    paths: list[Path] = []
    if primary.is_file():
        paths.append(primary)
    folder = primary.parent / "mailboxes"
    if folder.is_dir():
        paths.extend(sorted(p for p in folder.glob("*.json") if p.is_file()))
    return paths


def imap_password(config_path: Path, primary: Path) -> str | None:
    """Mailbox password. Never read from the json.

    The primary mailbox uses NEURA_IMAP_PASSWORD. The others use a <name>.password
    file next to the json. If it is missing, None: the cycle skips that mailbox.
    """
    config_path = Path(config_path)
    primary = Path(primary)
    if config_path.resolve() == primary.resolve():
        value = os.environ.get("NEURA_IMAP_PASSWORD", "").strip()
        return value or None
    secret = config_path.with_suffix(".password")
    if not secret.is_file():
        return None
    return secret.read_text(encoding="utf-8").strip() or None


def nightly_due(last_nightly_at: str | None, now: datetime) -> bool:
    """Dopo le 02:00 ora locale, una volta al giorno."""
    local_tz = datetime.now().astimezone().tzinfo
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    local = now.astimezone(local_tz)
    if local.hour < 2:
        return False
    if not last_nightly_at:
        return True
    last = datetime.fromisoformat(str(last_nightly_at).replace("Z", "+00:00")).astimezone(local_tz)
    return last.date() < local.date()


def build_classifier(
    mailbox: MailboxConfig,
    encoder: Encoder,
    data_root: Path,
    prior_net=None,
) -> Classifier:
    """State and registry for this mailbox. Uses the encoder it is given; it does not create another."""
    user_root = Path(data_root) / "users" / mailbox.user_id
    box_root = Path(data_root) / "mailboxes" / mailbox.mailbox_id
    state = UserState(
        user_root,
        user_id=mailbox.user_id,
        N=mailbox.N,
        order=mailbox.order,
        profile=mailbox.profile,
        encoder_name=encoder.name,
    )
    registry = Registry(box_root / "pred.sqlite")
    return Classifier(mailbox, state, encoder, registry, prior_net=prior_net)


def run_cycle(
    boxes: list[CycleMailbox],
    encoder: Encoder,
    data_root: Path,
    *,
    now: datetime | None = None,
    run_nightly: bool | None = None,
    progress: Callable[[str], None] | None = None,
    prior_net=None,
) -> list[dict]:
    """For each mailbox, under that user's lock: classify, and observe at night.

    run_nightly True forces observation, False skips it, None decides from the clock.
    An error on one mailbox does not stop the others.
    """
    from collections import Counter

    from neuraec.nightly import nightly, observe_moves, predict_unseen, write_notify_queue

    now = now or utcnow()
    if prior_net is None:
        from neuraec.prior_net import default_prior_path, load_accepted

        prior_net = load_accepted(default_prior_path())

    def say(message: str) -> None:
        if progress is not None:
            progress(message)

    results: list[dict] = []
    for box in boxes:
        mailbox = box.mailbox
        root = Path(data_root) / "users" / mailbox.user_id
        try:
            with user_dir_lock(root):
                clf = build_classifier(mailbox, encoder, data_root, prior_net=prior_net)
                say(f"mailbox {mailbox.mailbox_id}: classifying unread")
                with box.adapter:
                    labeled = predict_unseen(mailbox, box.adapter, clf, now=now)
                    say(f"labeled: {len(labeled)}")
                    write_notify_queue(mailbox, labeled, data_root, now=now)
                    counts = Counter(mailbox.label_for_rank(pred.rank) for _, pred in labeled)
                    for label, count in sorted(counts.items()):
                        say(f"new: {count} in {label}")
                    moves = observe_moves(mailbox, box.adapter, clf, now=now)
                    if moves.kpi.get("error"):
                        say(f"mailbox {mailbox.mailbox_id}: could not read moves: {moves.kpi['error']}")
                    elif moves.n_observed:
                        say(
                            f"mailbox {mailbox.mailbox_id}: learned {moves.n_corr} corrections "
                            f"and {moves.n_replied} replies from your moves"
                        )
                    due = run_nightly if run_nightly is not None else nightly_due(clf.state.last_nightly_at, now)
                    observed = None
                    night_error = None
                    if due:
                        from neuraec.constants import OBSERVE_DELAY_HOURS

                        ready = clf.registry.open_rows(older_than_hours=OBSERVE_DELAY_HOURS, now=now)
                        waiting = len(clf.registry.open_rows(now=now)) - len(ready)
                        say(
                            f"mailbox {mailbox.mailbox_id}: nightly observation, "
                            f"{len(ready)} ready, {waiting} still under 24 hours"
                        )
                        report = nightly(mailbox, box.adapter, clf, now=now)
                        observed = report.n_observed
                        night_error = report.kpi.get("error")
                        if night_error:
                            say(f"error {mailbox.mailbox_id}: {night_error}")
                        else:
                            say(
                                f"mailbox {mailbox.mailbox_id}: observed {report.n_observed}, "
                                f"corrections {report.n_corr}, confirmations {report.n_conf}, "
                                f"replies {report.n_replied}, deleted {report.n_deleted}, "
                                f"still unread {report.n_unread}"
                            )
                row = {
                    "mailbox_id": mailbox.mailbox_id,
                    "n_labeled": len(labeled),
                    "n_moves": moves.n_corr,
                    "n_observed": observed,
                }
                if night_error:
                    row["error"] = str(night_error)
                results.append(row)
        except Exception as exc:
            say(f"error {mailbox.mailbox_id}: {exc}")
            try:
                box.adapter.close()
            except Exception:
                pass
            results.append({"mailbox_id": mailbox.mailbox_id, "error": str(exc)})
    return results
