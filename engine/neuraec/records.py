from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

Order = Literal["desc", "asc"]
Source = Literal["corr", "conf", "manual", "replied"]
UserAction = Literal["moved", "read_unmoved", "replied", "deleted", "none", "manual"]
PredStatus = Literal["open", "resolved", "expired", "frozen"]
Stage = Literal["thread", "sender", "domain", "memory", "prior"]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def domain_of(addr: str) -> str:
    if not addr or "@" not in addr:
        return ""
    return addr.rsplit("@", 1)[1].lower()


def normalize_addr(addr: str | None) -> str:
    if not addr:
        return ""
    return str(addr).strip().lower()


@dataclass
class LabelMap:
    rank: int
    provider_label: str
    text: str


def folders_match(a: str, b: str) -> bool:
    """True if two IMAP folder names refer to the same mailbox."""
    if not a or not b:
        return False
    if a == b:
        return True

    def parts(name: str) -> str:
        return name.replace("/", ".").strip().lower()

    na, nb = parts(a), parts(b)
    if na == nb:
        return True
    return na.endswith("." + nb) or nb.endswith("." + na)


DEFAULT_LABEL_PREFIX = "Neura-P"


def priority_folder_name(rank: int, provider: str, prefix: str = DEFAULT_LABEL_PREFIX) -> str:
    stem = (prefix or DEFAULT_LABEL_PREFIX).strip().strip(".")
    numbered = f"{stem}{int(rank) + 1}"
    if provider == "imap" and not stem.upper().startswith("INBOX"):
        return f"INBOX.{numbered}"
    return numbered


def is_priority_name(name: str, prefix: str) -> bool:
    stem = (prefix or "").strip()
    if not name or not stem:
        return False
    leaf = name.replace("/", ".").split(".")[-1]
    if not leaf.startswith(stem):
        return False
    rest = leaf[len(stem) :]
    return rest.isdigit() and int(rest) >= 1


def infer_label_prefix(labels: list[LabelMap]) -> str:
    if not labels:
        return DEFAULT_LABEL_PREFIX
    leaf = labels[0].provider_label.replace("/", ".").split(".")[-1]
    digits = len(leaf) - len(leaf.rstrip("0123456789"))
    if digits and len(leaf) > digits:
        return leaf[:-digits]
    return DEFAULT_LABEL_PREFIX


def default_priority_labels(
    N: int,
    provider: str = "imap",
    prefix: str = DEFAULT_LABEL_PREFIX,
) -> list[LabelMap]:
    return [
        LabelMap(
            rank=r,
            provider_label=priority_folder_name(r, provider, prefix),
            text=f"Priority {r + 1}",
        )
        for r in range(int(N))
    ]


@dataclass
class MailboxConfig:
    mailbox_id: str
    user_id: str
    own_addresses: list[str]
    N: int
    order: Order = "desc"
    labels: list[LabelMap] = field(default_factory=list)
    contacts: list[str] = field(default_factory=list)
    host: str = ""
    username: str = ""
    port: int = 993
    tls: str = "ssl"
    provider: str = "imap"
    label_prefix: str = DEFAULT_LABEL_PREFIX
    profile: dict[str, list[str]] = field(default_factory=lambda: {"fig": [], "fun": [], "set": []})
    # Where classified mail lands: "move" into the priority folder, "label" stays in
    # the inbox with a label. IMAP has folders only; Gmail and Graph can do both.
    placement: str = ""

    def __post_init__(self) -> None:
        self.own_addresses = [normalize_addr(a) for a in self.own_addresses if a]
        self.contacts = [normalize_addr(a) for a in self.contacts if a]
        if self.N < 2:
            raise ValueError("N must be >= 2")
        if self.order not in ("desc", "asc"):
            raise ValueError("order must be desc or asc")
        if self.tls not in ("ssl", "starttls", "none"):
            raise ValueError("tls must be ssl, starttls or none")
        if self.provider not in ("imap", "gmail", "graph"):
            raise ValueError("provider must be imap, gmail or graph")
        if not self.placement:
            self.placement = "move" if self.provider == "imap" else "label"
        if self.placement not in ("move", "label"):
            raise ValueError("placement must be move or label")
        if self.provider == "imap":
            self.placement = "move"
        if not self.username and self.own_addresses:
            self.username = self.own_addresses[0]
        self.label_prefix = (self.label_prefix or DEFAULT_LABEL_PREFIX).strip() or DEFAULT_LABEL_PREFIX
        if not self.labels:
            self.labels = default_priority_labels(self.N, self.provider, self.label_prefix)
        if self.profile is None:
            self.profile = {"fig": [], "fun": [], "set": []}

    @property
    def own_set(self) -> set[str]:
        return set(self.own_addresses)

    @property
    def own_domains(self) -> set[str]:
        return {domain_of(a) for a in self.own_addresses if domain_of(a)}

    @property
    def contact_set(self) -> set[str]:
        return set(self.contacts)

    def label_for_rank(self, rank: int) -> str:
        """Folder for the internal rank. With order=asc, rank 0 lands on the last label."""
        from neuraec.ordinal import rank_to_label

        slot = rank_to_label(int(rank), self.N, self.order)
        for lab in self.labels:
            if lab.rank == slot:
                return lab.provider_label
        return f"P{slot + 1}"

    def rank_for_label(self, folder: str) -> int | None:
        """Internal rank of a folder. With order=asc, BeC-P1 is the least urgent rank."""
        from neuraec.ordinal import label_to_rank

        if not folder:
            return None
        for lab in self.labels:
            if folders_match(lab.provider_label, folder):
                return label_to_rank(lab.rank, self.N, self.order)
        return None

    def is_priority_folder(self, folder: str) -> bool:
        return self.rank_for_label(folder) is not None


@dataclass
class EmailRecord:
    uid: str
    message_id: str = ""
    in_reply_to: str | None = None
    references: list[str] = field(default_factory=list)
    thread_id: str | None = None
    received_at: datetime = field(default_factory=utcnow)
    from_addr: str = ""
    from_name: str = ""
    to_addrs: list[str] = field(default_factory=list)
    cc_addrs: list[str] = field(default_factory=list)
    subject: str = ""
    snippet: str = ""
    has_attachment: bool = False
    list_unsubscribe: bool = False
    list_id: bool = False
    precedence_bulk: bool = False
    auto_submitted: bool = False
    is_seen: bool = False
    is_answered: bool = False
    folder: str = ""

    def __post_init__(self) -> None:
        self.from_addr = normalize_addr(self.from_addr)
        self.to_addrs = [normalize_addr(a) for a in self.to_addrs if a]
        self.cc_addrs = [normalize_addr(a) for a in self.cc_addrs if a]
        if self.in_reply_to:
            self.in_reply_to = str(self.in_reply_to).strip()
        if self.message_id:
            self.message_id = str(self.message_id).strip()
        if self.received_at.tzinfo is None:
            self.received_at = self.received_at.replace(tzinfo=timezone.utc)

    @property
    def domain(self) -> str:
        return domain_of(self.from_addr)

    @property
    def thread_key(self) -> str:
        if self.thread_id:
            return self.thread_id
        if self.references:
            return self.references[0]
        if self.in_reply_to:
            return self.in_reply_to
        return self.message_id or self.uid

    def encoder_text(self, snippet_chars: int = 1000) -> str:
        snippet = (self.snippet or "")[:snippet_chars]
        return f"{self.subject or ''}\n{snippet}"


@dataclass
class Prediction:
    rank: int
    u: float                                  # urgenza attesa Σ_r P_r · u*(r), per registro e log
    conf: float                               # max confidenza fra gli stimatori
    stage: str                                # stimatore con confidenza massima
    parts: dict[str, tuple[float, float]]     # per stimatore: (urgenza attesa, confidenza)
    p: list[float] = field(default_factory=list)   # distribuzione combinata sui ranghi
    p_max: float = 0.0


@dataclass
class Observation:
    uid: str
    user_action: UserAction
    rank: int | None
    weight: float
    source: Source | None


@dataclass
class NightlyReport:
    n_observed: int = 0
    n_corr: int = 0
    n_conf: int = 0
    n_replied: int = 0
    n_expired: int = 0
    n_deleted: int = 0
    n_unread: int = 0
    n_predicted: int = 0
    kpi: dict = field(default_factory=dict)
