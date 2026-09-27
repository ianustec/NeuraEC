# -*- mode: python ; coding: utf-8 -*-
"""Freeze `python -m neuraec` into a standalone folder: dist/neura-engine/.

Usage: .venv/bin/pyinstaller packaging/neura-engine.spec
Copy that folder into the desktop app; the model lives beside it (see export_model.py).
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).resolve().parent

hidden = []
for pkg in ("sentence_transformers", "transformers", "tokenizers", "safetensors", "imap_tools"):
    hidden += collect_submodules(pkg)
hidden += [
    "neuraec.adapters.imap",
    "neuraec.adapters.gmail",
    "neuraec.adapters.graph",
    "neuraec.adapters.fake",
    "neuraec.auth_flow",
    "neuraec.oauth_store",
    "googleapiclient",
    "googleapiclient.discovery",
    "google.oauth2.credentials",
    "google_auth_oauthlib.flow",
    "msal",
    "requests",
    "sklearn.utils._cython_blas",
    "sklearn.neighbors._partition_nodes",
    "sklearn.tree._utils",
]

datas = [
    (str(ROOT / "neuraec" / "data"), "neuraec/data"),
]
datas += collect_data_files("sentence_transformers")
datas += collect_data_files("transformers", includes=["**/*.json", "**/*.txt"])
datas += collect_data_files("googleapiclient", includes=["discovery_cache/documents/gmail.*"])

# Non servono a classificare e pesano.
excludes = [
    "matplotlib",
    "IPython",
    "jupyter",
    "notebook",
    "pytest",
    "tkinter",
    "torch.utils.tensorboard",
    "torchvision",
    "torchaudio",
    "onnxruntime",
    "PIL",
    "pandas",
]

a = Analysis(
    [str(ROOT / "neuraec" / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="neura-engine",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="neura-engine",
)
