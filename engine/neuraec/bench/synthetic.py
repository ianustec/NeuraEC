from __future__ import annotations

from datetime import datetime, timedelta, timezone

from neuraec.records import EmailRecord, MailboxConfig


def mailbox(user_id: str, N: int = 4, order: str = "desc", tmp_contacts: list[str] | None = None) -> MailboxConfig:
    from neuraec.records import LabelMap

    return MailboxConfig(
        mailbox_id=f"mb-{user_id}",
        user_id=user_id,
        own_addresses=[f"{user_id}@azienda.it"],
        N=N,
        order=order,
        labels=[LabelMap(rank=r, provider_label=f"P{r}", text=f"Priority {r}") for r in range(N)],
        contacts=tmp_contacts or [],
    )


NEWSLETTER_TOKENS = (
    "newsletter promozione sconto offerta unsubscribe listino catalogo marketing campagna"
)
INVOICE_TOKENS = (
    "fattura invoice scadenza pagamento ordine fornitore bonifico addebito ricevuta"
)
OTHER_TOKENS = "riunione verbale appuntamento progetto aggiornamento interno nota"


def make_email(
    uid: str,
    kind: str,
    *,
    from_addr: str | None = None,
    to_me: bool = True,
    only_me: bool = True,
    cc_me: bool = False,
    n_to: int = 1,
    n_cc: int = 0,
    attachment: bool = False,
    is_reply: bool = False,
    bulk: bool = False,
    user_id: str = "a",
    minutes: int = 0,
    subject_extra: str = "",
) -> EmailRecord:
    own = f"{user_id}@azienda.it"
    if kind == "newsletter":
        subject = f"Newsletter promozione sconto {subject_extra}".strip()
        snippet = NEWSLETTER_TOKENS
        from_addr = from_addr or "news@promo.example"
        bulk = True
    elif kind == "invoice":
        subject = f"Fattura ordine pagamento {subject_extra}".strip()
        snippet = INVOICE_TOKENS
        from_addr = from_addr or "billing@fornitore.example"
    else:
        subject = f"Riunione progetto {subject_extra}".strip()
        snippet = OTHER_TOKENS
        from_addr = from_addr or "collega@azienda.it"

    to_addrs = []
    if to_me:
        to_addrs.append(own)
    extras = max(0, n_to - len(to_addrs))
    to_addrs.extend([f"altro{i}@esterno.it" for i in range(extras)])
    if only_me and to_me:
        to_addrs = [own]

    cc_addrs = []
    if cc_me:
        cc_addrs.append(own)
    extras_cc = max(0, n_cc - len(cc_addrs))
    cc_addrs.extend([f"cc{i}@esterno.it" for i in range(extras_cc)])

    received = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=minutes)
    return EmailRecord(
        uid=uid,
        message_id=f"<{uid}@test>",
        in_reply_to=f"<parent-{uid}@test>" if is_reply else None,
        received_at=received,
        from_addr=from_addr,
        to_addrs=to_addrs,
        cc_addrs=cc_addrs,
        subject=subject,
        snippet=snippet,
        has_attachment=attachment,
        list_unsubscribe=bulk,
        list_id=bulk,
        precedence_bulk=bulk,
    )


def opposite_policy_corpus(n: int = 200, user_id: str = "a") -> list[tuple[EmailRecord, str]]:
    """n emails labelled by kind. kind in {newsletter, invoice}."""
    out = []
    for i in range(n):
        kind = "newsletter" if i % 2 == 0 else "invoice"
        rec = make_email(
            f"{user_id}-{kind}-{i}",
            kind,
            from_addr=f"{kind}{i % 17}@mail.example",
            user_id=user_id,
            minutes=i,
            subject_extra=str(i),
        )
        out.append((rec, kind))
    return out
