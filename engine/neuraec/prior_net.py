"""Prior v1: MLP 401→128→32→1, inferenza numpy. Il training sta in prior_train.py."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from neuraec.constants import ENCODER_DIM

IN_DIM = ENCODER_DIM + 11 + 3 + 3  # e, s, r, sim
H1 = 128
H2 = 32


def pack_features(e: np.ndarray, s: np.ndarray, r: np.ndarray, sim: np.ndarray) -> np.ndarray:
    parts = [np.asarray(v, dtype=np.float64).reshape(-1) for v in (e, s, r, sim)]
    x = np.concatenate(parts)
    if x.shape[0] != IN_DIM:
        raise ValueError(f"ingresso prior {x.shape[0]} != {IN_DIM}")
    return x


class PriorNet:
    """Weights as numpy arrays (in, out). accepted=False: the classifier does not use it."""

    def __init__(
        self,
        W1: np.ndarray,
        b1: np.ndarray,
        W2: np.ndarray,
        b2: np.ndarray,
        W3: np.ndarray,
        b3: np.ndarray,
        *,
        accepted: bool = False,
        mae_v0: float | None = None,
        mae_v1: float | None = None,
    ) -> None:
        self.W1 = np.asarray(W1, dtype=np.float64)
        self.b1 = np.asarray(b1, dtype=np.float64).reshape(-1)
        self.W2 = np.asarray(W2, dtype=np.float64)
        self.b2 = np.asarray(b2, dtype=np.float64).reshape(-1)
        self.W3 = np.asarray(W3, dtype=np.float64).reshape(H2, 1)
        self.b3 = np.asarray(b3, dtype=np.float64).reshape(1)
        self.accepted = bool(accepted)
        self.mae_v0 = mae_v0
        self.mae_v1 = mae_v1
        if self.W1.shape != (IN_DIM, H1) or self.W2.shape != (H1, H2):
            raise ValueError(f"forme pesi inattese: {self.W1.shape}, {self.W2.shape}")

    def urgency(self, e: np.ndarray, s: np.ndarray, r: np.ndarray, sim: np.ndarray) -> float:
        x = pack_features(e, s, r, sim)
        h = np.maximum(0.0, x @ self.W1 + self.b1)
        h = np.maximum(0.0, h @ self.W2 + self.b2)
        z = float(h @ self.W3[:, 0] + self.b3[0])
        return float(1.0 / (1.0 + np.exp(-z)))

    def save(self, path: Path | str) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            path,
            W1=self.W1,
            b1=self.b1,
            W2=self.W2,
            b2=self.b2,
            W3=self.W3,
            b3=self.b3,
            accepted=np.float64(1.0 if self.accepted else 0.0),
            mae_v0=np.float64(self.mae_v0 if self.mae_v0 is not None else np.nan),
            mae_v1=np.float64(self.mae_v1 if self.mae_v1 is not None else np.nan),
        )

    @classmethod
    def load(cls, path: Path | str) -> PriorNet:
        with np.load(path) as data:
            mae_v0 = float(data["mae_v0"]) if "mae_v0" in data else None
            mae_v1 = float(data["mae_v1"]) if "mae_v1" in data else None
            return cls(
                data["W1"],
                data["b1"],
                data["W2"],
                data["b2"],
                data["W3"],
                data["b3"],
                accepted=bool(float(data["accepted"]) >= 0.5) if "accepted" in data else False,
                mae_v0=None if mae_v0 is None or np.isnan(mae_v0) else mae_v0,
                mae_v1=None if mae_v1 is None or np.isnan(mae_v1) else mae_v1,
            )


def load_accepted(path: Path | str) -> PriorNet | None:
    """None when the file is missing or accepted is false: v0 stays in use."""
    path = Path(path)
    if not path.exists():
        return None
    net = PriorNet.load(path)
    return net if net.accepted else None


def default_prior_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "prior_v1.npz"
