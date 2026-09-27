from __future__ import annotations

import hashlib
import os
import re
import sys
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np

from neuraec.constants import ENCODER_DIM, FAKE_ENCODER_NAME, DEFAULT_ENCODER_NAME

_TOKEN = re.compile(r"[0-9a-zàèéìòùäöüßáíóúñç]+", re.IGNORECASE)


def local_model_dir(model_name: str) -> Path | None:
    """Folder holding the model weights, when the app ships them.

    NEURA_MODEL_DIR points at the model folder, or at a folder that contains it.
    con il suo nome. Senza variabile si guarda accanto all'eseguibile congelato.
    """
    candidates: list[Path] = []
    env = os.environ.get("NEURA_MODEL_DIR", "").strip()
    if env:
        candidates.append(Path(env))
        candidates.append(Path(env) / model_name)
    frozen = getattr(sys, "_MEIPASS", None)
    if frozen:
        candidates.append(Path(frozen) / "model" / model_name)
    for candidate in candidates:
        if (candidate / "modules.json").exists() or (candidate / "config.json").exists():
            return candidate
    return None


def l2_normalize(vec: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(vec))
    if n == 0.0:
        return vec.astype(np.float32)
    return (vec / n).astype(np.float32)


def strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


class Encoder(ABC):
    name: str = "encoder"
    dim: int = ENCODER_DIM

    @abstractmethod
    def encode(self, text: str) -> np.ndarray:
        """Return an L2-normalized float32 vector of size dim."""

    def encode_many(self, texts: list[str]) -> np.ndarray:
        return np.stack([self.encode(t) for t in texts], axis=0)


class FakeEncoder(Encoder):
    """Deterministic bag-of-tokens hashing encoder. No model download."""

    name = FAKE_ENCODER_NAME
    dim = ENCODER_DIM

    def encode(self, text: str) -> np.ndarray:
        tokens = _TOKEN.findall(strip_html(text).lower())
        vec = np.zeros(self.dim, dtype=np.float32)
        for token in tokens:
            digest = hashlib.md5(token.encode("utf-8")).digest()
            seed = int.from_bytes(digest[:8], "little") % (2**32)
            rng = np.random.RandomState(seed)
            vec += rng.randn(self.dim).astype(np.float32)
        return l2_normalize(vec)


class SentenceEncoder(Encoder):
    """Lazy wrapper around paraphrase-multilingual-MiniLM-L12-v2."""

    name = DEFAULT_ENCODER_NAME
    dim = ENCODER_DIM

    def __init__(self, model_name: str = DEFAULT_ENCODER_NAME) -> None:
        self.name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            local = local_model_dir(self.name)
            if local is not None:
                # Pesi dentro l'app: niente rete, niente cache Hugging Face.
                os.environ.setdefault("HF_HUB_OFFLINE", "1")
                os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
                self._model = SentenceTransformer(str(local), local_files_only=True)
            else:
                self._model = SentenceTransformer(self.name)
        return self._model

    def encode(self, text: str) -> np.ndarray:
        model = self._load()
        vec = model.encode(
            strip_html(text),
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        vec = np.asarray(vec, dtype=np.float32).reshape(-1)
        if vec.shape[0] != self.dim:
            # pad or project by truncation / zero-pad
            out = np.zeros(self.dim, dtype=np.float32)
            n = min(self.dim, vec.shape[0])
            out[:n] = vec[:n]
            return l2_normalize(out)
        return l2_normalize(vec)

    def encode_many(self, texts: list[str]) -> np.ndarray:
        model = self._load()
        cleaned = [strip_html(t) for t in texts]
        vecs = model.encode(
            cleaned,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        out = np.asarray(vecs, dtype=np.float32)
        if out.ndim == 1:
            out = out.reshape(1, -1)
        if out.shape[1] != self.dim:
            fixed = np.zeros((out.shape[0], self.dim), dtype=np.float32)
            n = min(self.dim, out.shape[1])
            fixed[:, :n] = out[:, :n]
            norms = np.linalg.norm(fixed, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            return (fixed / norms).astype(np.float32)
        return out


def try_sentence_encoder() -> SentenceEncoder | None:
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        return None
    return SentenceEncoder()
