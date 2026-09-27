"""Save the MiniLM weights into a plain folder, to ship inside the app.

Uso: .venv/bin/python packaging/export_model.py dist/model
Scrive dist/model/<nome modello>/ con modules.json, config, tokenizer e pesi.
The first run downloads from Hugging Face; after that the app does not need the network.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from neuraec.constants import DEFAULT_ENCODER_NAME  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: export_model.py <destination folder>", file=sys.stderr)
        return 2
    target = Path(argv[1]).resolve() / DEFAULT_ENCODER_NAME
    if (target / "modules.json").exists():
        print(f"model already present: {target}")
        return 0
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(DEFAULT_ENCODER_NAME)
    target.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(target))
    print(f"modello salvato in {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
