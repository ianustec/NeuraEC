# NEURA desktop

Finestra per Windows, Mac e Linux. Classifica la posta lanciando il motore Python: quello congelato dentro l'app, se c'è, altrimenti `../engine`. Non passa dallo store.

La password sta in `~/.neura/password`. Host, utente e numero di priorità stanno in `~/.neura/mailbox.json`. Lo stato e il registro stanno in `~/.neura/data`.

## Avvio in sviluppo

```bash
cd app
flutter run -d macos
```

Su Linux e Windows, dalla stessa cartella: `flutter run -d linux` oppure `flutter run -d windows`.

## Build da distribuire

### macOS: app autonoma in un `.dmg`

```bash
app/tool/build_mac.sh
```

Produce `dist/NeuraEC.dmg` (circa 750 MB, 1,3 GB installata) con dentro tutto: la finestra, il motore Python congelato con PyInstaller in `Contents/Resources/engine` e i pesi MiniLM in `Contents/Resources/model`. Sul Mac del collega non serve Python, né il virtualenv, né la rete al primo avvio. Solo Apple Silicon: il motore viene dal Python arm64 del Mac che costruisce.

Richiede sul Mac che costruisce: il venv in `../engine/.venv` con `pip install -e ".[encoder,gmail,graph]"`, Flutter, Xcode. Il modello viene scaricato una volta in `../engine/dist/model`. `SKIP_ENGINE=1` riusa il motore congelato se il Python non è cambiato.

Senza `NEURA_SIGN_IDENTITY` la firma è ad hoc e Gatekeeper blocca l'app («non è stata aperta»): si supera solo da Impostazioni → Privacy e sicurezza → Apri comunque. Per distribuirla senza avvisi:

```bash
NEURA_SIGN_IDENTITY="Developer ID Application: IANUSTEC (TEAMID)" \
NEURA_NOTARY_PROFILE=neuraec tool/build_mac.sh
```

Serve una volta sola, sul Mac che costruisce:

1. Certificato **Developer ID Application** da developer.apple.com → Certificates (lo può creare solo l'Account Holder del team), installato nella keychain. `security find-identity -v -p codesigning` deve mostrarlo.
2. Credenziali per la notarizzazione: `xcrun notarytool store-credentials neuraec --apple-id <Apple ID> --team-id <TEAMID> --password <password specifica per app>`. La password per app si genera su appleid.apple.com → Accesso e sicurezza.

Lo script firma il motore con `Engine.entitlements` (hardened runtime con memoria eseguibile e librerie non validate, necessari a Python), notarizza l'app, sigilla il ticket, poi firma, notarizza e sigilla il `.dmg`. Il collega apre l'app con un doppio clic.

Chi apre l'app la trova in `Applicazioni`; i dati restano in `~/.neura`, con casella, password e collegamenti Google o Microsoft inseriti da Caselle.

### Sviluppo e altre piattaforme

```bash
flutter build macos
flutter build linux
flutter build windows
```

Senza motore integrato l'app cerca `../engine/.venv`, oppure `NEURA_PYTHON` e `NEURA_PROJECT`. Su Windows e Linux il motore congelato va in `engine/neura-engine(.exe)` e il modello in `model/`, accanto all'eseguibile.
