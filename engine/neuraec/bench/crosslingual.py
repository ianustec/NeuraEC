from __future__ import annotations

import html
import re
import sys
from pathlib import Path

import numpy as np

from neuraec.bench.prequential import load_csv
from neuraec.encoder import SentenceEncoder, try_sentence_encoder


_URL = re.compile(r"https?://\S+|www\.\S+")
_ZW = re.compile(r"[\u200b\u200c\u200d\u2060\ufeff\u00a0]+")
_SEP = re.compile(r"([^\w\s]){3,}")
_WS = re.compile(r"\s+")


def _clean_for_mt(text: str) -> str:
    """The translator fails on URLs, HTML entities and separators; the encoder does not. They are stripped for a fair comparison."""
    text = html.unescape(text)
    text = _ZW.sub("", text)
    text = _URL.sub(" ", text)
    text = _SEP.sub(" ", text)
    return _WS.sub(" ", text).strip()


def _italian_subjects(csv_path: Path | None = None, limit: int = 300) -> list[str]:
    rows = load_csv(csv_path)
    texts = []
    for row in rows:
        lang = str(row.get("detected_language") or "")
        if lang and lang != "it":
            continue
        subj = str(row.get("subject") or "")
        snip = str(row.get("snippet") or "")
        text = _clean_for_mt(f"{subj}. {snip}")
        if len(text) < 40:
            continue
        texts.append(text[:800])
        if len(texts) >= limit:
            break
    return texts


def _try_opus(src: str, tgt: str):
    """Opus-MT: prima la copia locale del prototipo, poi il modello pubblico. Solo per il banco."""
    try:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    except ImportError:
        return None
    nmt_root = Path("/Users/thomasbenedetti/Desktop/bentho/EmailClassifier/NMT")
    candidates = [str(nmt_root / f"{src}_{tgt}"), f"Helsinki-NLP/opus-mt-{src}-{tgt}"]
    tok = model = None
    for name in candidates:
        try:
            tok = AutoTokenizer.from_pretrained(name)
            model = AutoModelForSeq2SeqLM.from_pretrained(name)
            break
        except Exception:
            tok = model = None
    if model is None:
        return None

    def translate(texts: list[str]) -> list[str]:
        out = []
        for text in texts:
            inputs = tok(text, return_tensors="pt", truncation=True, max_length=256)
            ids = model.generate(**inputs, max_new_tokens=200, num_beams=2)
            out.append(tok.decode(ids[0], skip_special_tokens=True))
        return out

    return translate


SRC_CHARS = 400  # stesso troncamento per sorgente e traduzione: il confronto deve essere equo


def run_alignment(encoder: SentenceEncoder, n: int = 300) -> dict | None:
    texts = _italian_subjects(limit=n)
    if len(texts) < 20:
        print("too few Italian texts in the CSV", file=sys.stderr)
        return None
    translate = _try_opus("it", "en")
    if translate is None:
        print("Opus-MT it_en not loadable; skip cross-lingua.", file=sys.stderr)
        return None
    # keep the first 40 to stay reasonable without a GPU
    sample = [t[:SRC_CHARS] for t in texts[:40]]
    translated = translate(sample)
    e_src = encoder.encode_many(sample)
    e_tgt = encoder.encode_many(translated)
    cos = np.sum(e_src * e_tgt, axis=1)
    worst = int(np.argmin(cos))
    return {
        "n": len(sample),
        "median": float(np.median(cos)),
        "p10": float(np.quantile(cos, 0.10)),
        "pass_median": float(np.median(cos)) >= 0.80,
        "pass_p10": float(np.quantile(cos, 0.10)) >= 0.65,
        "worst": {"cos": float(cos[worst]), "src": sample[worst][:120], "tgt": translated[worst][:120]},
    }


def main() -> int:
    enc = try_sentence_encoder()
    if enc is None:
        print("sentence-transformers not installed; skip cross-lingua.")
        return 0
    try:
        enc.encode("prova")
    except Exception as exc:
        print(f"MiniLM not available ({exc}); skip cross-lingua.")
        return 0
    result = run_alignment(enc)
    if result is None:
        return 0
    print(
        f"alignment n={result['n']} median={result['median']:.3f} "
        f"p10={result['p10']:.3f} pass_median={result['pass_median']} pass_p10={result['pass_p10']}"
    )
    w = result["worst"]
    print(f"worst cos={w['cos']:.3f}\n  src: {w['src']!r}\n  tgt: {w['tgt']!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
