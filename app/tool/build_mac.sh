#!/bin/sh
# Costruisce NeuraEC per macOS come app autonoma e la impacchetta in un .dmg.
#
#   app/tool/build_mac.sh                  -> dist/NeuraEC.dmg, firma ad hoc (Gatekeeper la blocca)
#   SKIP_ENGINE=1 tool/build_mac.sh        riusa il motore congelato, se il Python non e' cambiato
#
# Distribuzione vera, senza avvisi di Gatekeeper:
#   NEURA_SIGN_IDENTITY="Developer ID Application: IANUSTEC (TEAMID)" \
#   NEURA_NOTARY_PROFILE=neuraec tool/build_mac.sh
# Il certificato Developer ID Application deve stare nella keychain; il profilo notary si crea una volta con
#   xcrun notarytool store-credentials neuraec --apple-id ... --team-id ... --password <password per app>
# Senza NEURA_SIGN_IDENTITY la firma e' ad hoc e non si notarizza.
#
# Dentro l'app finiscono:
#   Contents/Resources/engine/   motore Python congelato con PyInstaller
#   Contents/Resources/model/        pesi MiniLM, così non serve la rete
set -eu

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENGINE_DIR="$(cd "$APP_DIR/../engine" && pwd)"
FLUTTER="${FLUTTER:-$(command -v flutter || echo "$HOME/flutter/bin/flutter")}"
PYTHON="$ENGINE_DIR/.venv/bin/python"
OUT="$APP_DIR/dist"
# Fuori dal progetto: su iCloud gli attributi estesi ricompaiono e codesign li rifiuta.
STAGE="$(mktemp -d /tmp/neuraec-stage.XXXX)"
trap 'rm -rf "$STAGE"' EXIT
APP_NAME="NeuraEC"
BUNDLE_SRC="$APP_DIR/build/macos/Build/Products/Release/neura_app.app"
IDENTITY="${NEURA_SIGN_IDENTITY:--}"
NOTARY="${NEURA_NOTARY_PROFILE:-}"

step() { printf '\n== %s\n' "$1"; }

if [ "$IDENTITY" != "-" ]; then
  security find-identity -v -p codesigning | grep -q "$IDENTITY" \
    || { echo "certificato non trovato nella keychain: $IDENTITY"; security find-identity -v -p codesigning; exit 1; }
  [ -n "$NOTARY" ] || echo "avviso: senza NEURA_NOTARY_PROFILE l'app viene firmata ma non notarizzata"
fi

step "motore: dipendenze"
[ -x "$PYTHON" ] || { echo "manca $PYTHON: crea il venv del classificatore"; exit 1; }
"$PYTHON" -m pip install -q -e "$ENGINE_DIR[encoder,gmail,graph]" pyinstaller

step "motore: pesi del modello"
"$PYTHON" "$ENGINE_DIR/packaging/export_model.py" "$ENGINE_DIR/dist/model"

step "motore: congelamento"
if [ "${SKIP_ENGINE:-0}" = "1" ] && [ -x "$ENGINE_DIR/dist/neura-engine/neura-engine" ]; then
  echo "uso il motore già congelato (SKIP_ENGINE=1)"
else
  (cd "$ENGINE_DIR" && "$ENGINE_DIR/.venv/bin/pyinstaller" --noconfirm \
    --workpath build/pyinstaller --distpath dist packaging/neura-engine.spec >"$ENGINE_DIR/build/pyinstaller.log" 2>&1) \
    || { tail -30 "$ENGINE_DIR/build/pyinstaller.log"; exit 1; }
fi

step "finestra: flutter build macos --release"
(cd "$APP_DIR" && "$FLUTTER" build macos --release)

step "bundle: copia del motore e del modello"
mkdir -p "$OUT"
APP="$STAGE/$APP_NAME.app"
# Il motore sta in Resources: in Helpers o Frameworks codesign tratta ogni cartella
# `.dist-info` come bundle annidato e rifiuta la firma.
ENGINE="$APP/Contents/Resources/engine"
ditto --norsrc --noextattr "$BUNDLE_SRC" "$APP"
ditto --norsrc --noextattr "$ENGINE_DIR/dist/neura-engine" "$ENGINE"
ditto --norsrc --noextattr "$ENGINE_DIR/dist/model" "$APP/Contents/Resources/model"
xattr -cr "$APP" || true

step "firma"
# Dal basso verso l'alto: ogni Mach-O del motore, il framework Python,
# poi i framework della finestra, infine l'app. La notarizzazione controlla
# ognuno e vuole Developer ID, hardened runtime e timestamp.
ENGINE_ENT="$APP_DIR/macos/Runner/Engine.entitlements"
APP_ENT="$APP_DIR/macos/Runner/Release.entitlements"
sign_engine() {
  # $@: file Mach-O del motore. Con Developer ID serve l'hardened runtime,
  # e per Python servono gli entitlement che allentano memoria eseguibile e validazione librerie.
  if [ "$IDENTITY" = "-" ]; then
    codesign --force --sign - "$@"
  else
    codesign --force --options runtime --timestamp --entitlements "$ENGINE_ENT" --sign "$IDENTITY" "$@"
  fi
}
sign_plain() {
  # $1: framework o libreria della finestra. Stesso certificato dell'app, senza entitlement di Python.
  if [ "$IDENTITY" = "-" ]; then
    codesign --force --sign - "$1"
  else
    codesign --force --options runtime --timestamp --sign "$IDENTITY" "$1"
  fi
}
find "$ENGINE" -type f \( -name '*.so' -o -name '*.dylib' \) -print0 \
  | while IFS= read -r -d '' f; do sign_engine "$f"; done
find "$ENGINE" -type f -perm -u+x ! -name '*.so' ! -name '*.dylib' ! -name '*.py' \
  ! -path '*dist-info*' -print0 \
  | while IFS= read -r -d '' f; do
      file -b "$f" | grep -q 'Mach-O' && sign_engine "$f"
    done
[ -d "$ENGINE/_internal/Python.framework" ] && sign_engine "$ENGINE/_internal/Python.framework"
sign_engine "$ENGINE/neura-engine"
if [ -d "$APP/Contents/Frameworks" ]; then
  find "$APP/Contents/Frameworks" -type f \( -name '*.dylib' -o -name '*.so' \) -print0 \
    | while IFS= read -r -d '' f; do sign_plain "$f"; done
  find "$APP/Contents/Frameworks" -depth -type d -name '*.framework' -print0 \
    | while IFS= read -r -d '' fw; do sign_plain "$fw"; done
fi
if [ "$IDENTITY" = "-" ]; then
  codesign --force --sign - "$APP"
else
  codesign --force --options runtime --timestamp \
    --entitlements "$APP_ENT" \
    --sign "$IDENTITY" "$APP/Contents/MacOS/neura_app"
  codesign --force --options runtime --timestamp \
    --entitlements "$APP_ENT" \
    --sign "$IDENTITY" "$APP"
  codesign -dvvv "$APP/Contents/Frameworks/FlutterMacOS.framework" 2>&1 | grep -q 'Developer ID Application' \
    || { echo "FlutterMacOS.framework non risulta firmato con Developer ID"; exit 1; }
fi
codesign --verify --strict "$APP"

notarize() {
  # $1: file da inviare (zip dell'app o dmg). Aspetta il verdetto di Apple.
  xcrun notarytool submit "$1" --keychain-profile "$NOTARY" --wait --output-format plist >"$STAGE/notary.plist"
  status="$(plutil -extract status raw -o - "$STAGE/notary.plist" 2>/dev/null || echo "?")"
  if [ "$status" != "Accepted" ]; then
    id="$(plutil -extract id raw -o - "$STAGE/notary.plist" 2>/dev/null || true)"
    echo "notarizzazione respinta ($status). Dettagli:"
    [ -n "$id" ] && xcrun notarytool log "$id" --keychain-profile "$NOTARY" || true
    exit 1
  fi
}

if [ "$IDENTITY" != "-" ] && [ -n "$NOTARY" ]; then
  step "notarizzazione dell'app"
  ditto -c -k --norsrc --keepParent "$STAGE/$APP_NAME.app" "$STAGE/$APP_NAME.zip"
  notarize "$STAGE/$APP_NAME.zip"
  xcrun stapler staple "$STAGE/$APP_NAME.app"
  rm -f "$STAGE/$APP_NAME.zip"
fi

step "prova: il motore integrato carica il modello"
HF_HUB_OFFLINE=1 NEURA_MODEL_DIR="$STAGE/$APP_NAME.app/Contents/Resources/model" \
  "$STAGE/$APP_NAME.app/Contents/Resources/engine/neura-engine" encoder 2>/dev/null | grep '^encoder' \
  || { echo "il motore integrato non carica il modello"; exit 1; }

step "dmg"
IMG="$STAGE/img"
mkdir -p "$IMG"
ditto --norsrc --noextattr "$STAGE/$APP_NAME.app" "$IMG/$APP_NAME.app"
ln -sfn /Applications "$IMG/Applications"
DMG="$STAGE/$APP_NAME.dmg"
hdiutil create -volname "$APP_NAME" -srcfolder "$IMG" -ov -format UDZO -quiet "$DMG"
if [ "$IDENTITY" != "-" ]; then
  codesign --force --timestamp --sign "$IDENTITY" "$DMG"
  if [ -n "$NOTARY" ]; then
    step "notarizzazione del dmg"
    notarize "$DMG"
    xcrun stapler staple "$DMG"
    spctl --assess --type open --context context:primary-signature -v "$DMG"
  fi
fi
mkdir -p "$OUT"
rm -f "$OUT/$APP_NAME.dmg"
rm -rf "$OUT/$APP_NAME.app"
ditto --norsrc "$DMG" "$OUT/$APP_NAME.dmg"
ditto --norsrc "$STAGE/$APP_NAME.app" "$OUT/$APP_NAME.app"

du -sh "$OUT/$APP_NAME.app" "$OUT/$APP_NAME.dmg"
echo "pronto: $OUT/$APP_NAME.dmg"
