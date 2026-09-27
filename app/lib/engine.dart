import 'dart:convert';
import 'dart:io';

import 'mailbox_config.dart';

class OAuthClients {
  const OAuthClients({
    this.gmailClientId = '',
    this.gmailClientSecret = '',
    this.graphClientId = '',
    this.graphTenant = 'common',
  });

  final String gmailClientId;
  final String gmailClientSecret;
  final String graphClientId;
  final String graphTenant;

  bool get gmailReady => gmailClientId.trim().isNotEmpty && gmailClientSecret.trim().isNotEmpty;
  bool get graphReady => graphClientId.trim().isNotEmpty;
}

class EngineResult {
  EngineResult(this.exitCode, this.stdoutText, this.stderrText);

  final int exitCode;
  final String stdoutText;
  final String stderrText;

  bool get ok => exitCode == 0;
}

/// Lancia `python -m neuraec` nel progetto del classificatore.
class NeuraEngine {
  NeuraEngine({Directory? home, this.python, this.project}) : home = home ?? defaultHome();

  final Directory home;
  final String? python;
  final String? project;

  File get configFile => File('${home.path}/mailbox.json');
  File get passwordFile => File('${home.path}/password');
  Directory get dataDir => Directory('${home.path}/data');
  File get logFile => File('${home.path}/neura.log');
  File get serviceFile => File('${home.path}/service.json');

  static Directory defaultHome() {
    final env = Platform.environment;
    final root = env['HOME'] ?? env['USERPROFILE'] ?? Directory.current.path;
    return Directory('$root/.neura');
  }

  Future<void> ensureLayout() async {
    await home.create(recursive: true);
    await dataDir.create(recursive: true);
  }

  Future<MailboxConfig> loadConfig() async {
    if (!configFile.existsSync()) return MailboxConfig.initial();
    final json = jsonDecode(await configFile.readAsString()) as Map<String, dynamic>;
    return MailboxConfig.fromJson(json);
  }

  Future<void> saveConfig(MailboxConfig config) async {
    await ensureLayout();
    await configFile.writeAsString('${config.encode()}\n');
  }

  Future<String> loadPassword() async {
    if (!passwordFile.existsSync()) return '';
    return (await passwordFile.readAsString()).trim();
  }

  Future<void> savePassword(String password) async {
    await _writeSecret(passwordFile, password);
  }

  Future<bool> loadNotificationsOn() async {
    if (!serviceFile.existsSync()) return true;
    try {
      final json = jsonDecode(await serviceFile.readAsString());
      if (json is Map && json['notifications'] is bool) return json['notifications'] as bool;
    } catch (_) {}
    return true;
  }

  Future<void> saveNotificationsOn(bool on) async {
    await ensureLayout();
    Map<String, dynamic> current = {};
    if (serviceFile.existsSync()) {
      try {
        final json = jsonDecode(await serviceFile.readAsString());
        if (json is Map<String, dynamic>) current = json;
      } catch (_) {}
    }
    current['notifications'] = on;
    await serviceFile.writeAsString('${const JsonEncoder.withIndent('  ').convert(current)}\n');
  }

  static const intervalChoices = [1, 5, 15];

  Future<int> loadIntervalMinutes() async {
    if (!serviceFile.existsSync()) return 5;
    try {
      final json = jsonDecode(await serviceFile.readAsString());
      if (json is Map) {
        final minutes = json['interval_minutes'];
        if (minutes is num && intervalChoices.contains(minutes.toInt())) return minutes.toInt();
      }
    } catch (_) {}
    return 5;
  }

  Future<void> saveIntervalMinutes(int minutes) async {
    final value = intervalChoices.contains(minutes) ? minutes : 5;
    await ensureLayout();
    Map<String, dynamic> current = {};
    if (serviceFile.existsSync()) {
      try {
        final json = jsonDecode(await serviceFile.readAsString());
        if (json is Map<String, dynamic>) current = json;
      } catch (_) {}
    }
    current['interval_minutes'] = value;
    await serviceFile.writeAsString('${const JsonEncoder.withIndent('  ').convert(current)}\n');
  }

  File get oauthFile => File('${home.path}/oauth.json');

  Future<OAuthClients> loadOAuth() async {
    if (!oauthFile.existsSync()) return const OAuthClients();
    final data = jsonDecode(await oauthFile.readAsString()) as Map<String, dynamic>;
    return OAuthClients(
      gmailClientId: (data['gmail_client_id'] ?? '').toString(),
      gmailClientSecret: (data['gmail_client_secret'] ?? '').toString(),
      graphClientId: (data['graph_client_id'] ?? '').toString(),
      graphTenant: (data['graph_tenant'] ?? 'common').toString(),
    );
  }

  Future<void> saveOAuth(OAuthClients clients) async {
    await ensureLayout();
    final payload = {
      'gmail_client_id': clients.gmailClientId.trim(),
      'gmail_client_secret': clients.gmailClientSecret.trim(),
      'graph_client_id': clients.graphClientId.trim(),
      'graph_tenant': clients.graphTenant.trim().isEmpty ? 'common' : clients.graphTenant.trim(),
    };
    await oauthFile.writeAsString('${const JsonEncoder.withIndent('  ').convert(payload)}\n');
    if (!Platform.isWindows) {
      await Process.run('chmod', ['600', oauthFile.path]);
    }
  }

  Future<bool> hasToken(String? configPath) async {
    if (configPath == null) return false;
    final file = File(configPath.replaceFirst(RegExp(r'\.json$'), '.token'));
    if (!file.existsSync()) return false;
    final data = jsonDecode(await file.readAsString());
    if (data is! Map) return false;
    return (data['refresh_token'] ?? '').toString().trim().isNotEmpty;
  }

  Directory get mailboxesDir => Directory('${home.path}/mailboxes');

  Future<List<MailboxSlot>> loadSlots() async {
    await ensureLayout();
    final slots = <MailboxSlot>[];
    if (configFile.existsSync()) {
      final json = jsonDecode(await configFile.readAsString()) as Map<String, dynamic>;
      slots.add(
        MailboxSlot(
          config: MailboxConfig.fromJson(json),
          password: await loadPassword(),
          primary: true,
          path: configFile.path,
        ),
      );
    } else {
      slots.add(MailboxSlot(config: MailboxConfig.initial(), password: '', primary: true, path: configFile.path));
    }
    if (mailboxesDir.existsSync()) {
      final files = mailboxesDir
          .listSync()
          .whereType<File>()
          .where((file) => file.path.endsWith('.json'))
          .toList()
        ..sort((a, b) => a.path.compareTo(b.path));
      for (final file in files) {
        final json = jsonDecode(await file.readAsString()) as Map<String, dynamic>;
        final secret = File(file.path.replaceFirst(RegExp(r'\.json$'), '.password'));
        final password = secret.existsSync() ? (await secret.readAsString()).trim() : '';
        slots.add(
          MailboxSlot(
            config: MailboxConfig.fromJson(json),
            password: password,
            primary: false,
            path: file.path,
          ),
        );
      }
    }
    return slots;
  }

  Future<MailboxSlot> saveSlot(MailboxSlot slot) async {
    await ensureLayout();
    if (slot.primary) {
      await saveConfig(slot.config);
      await savePassword(slot.password);
      return slot.copy(path: configFile.path);
    }
    final id = slot.config.mailboxId.trim();
    if (id.isEmpty) {
      throw StateError('casella senza id');
    }
    await mailboxesDir.create(recursive: true);
    final file = File('${mailboxesDir.path}/$id.json');
    await file.writeAsString('${slot.config.encode()}\n');
    await _writeSecret(File('${mailboxesDir.path}/$id.password'), slot.password);
    return slot.copy(path: file.path);
  }

  /// True se la casella è già stata preparata: cartelle create e inviate lette.
  Future<bool> isPrepared(MailboxSlot slot) async {
    final userId = slot.config.userId.trim();
    if (userId.isEmpty) return false;
    final stateFile = File('${dataDir.path}/users/$userId/state.json');
    if (stateFile.existsSync()) {
      final meta = jsonDecode(await stateFile.readAsString());
      if (meta is Map && meta['initialized_at'] != null) return true;
    }
    final replied = File('${dataDir.path}/users/$userId/replied.json');
    if (!replied.existsSync()) return false;
    final text = (await replied.readAsString()).trim();
    return text.isNotEmpty && text != '{}';
  }

  /// Clears the dashboard numbers for one mailbox. Learning stays on disk.
  Future<void> resetStats(MailboxSlot slot) async {
    final id = slot.config.mailboxId.trim();
    if (id.isEmpty) return;
    final dir = Directory('${dataDir.path}/mailboxes/$id');
    if (!dir.existsSync()) return;
    for (final name in const ['pred.sqlite', 'pred.sqlite-wal', 'pred.sqlite-shm']) {
      final file = File('${dir.path}/$name');
      if (file.existsSync()) await file.delete();
    }
  }

  Future<void> deleteSlot(MailboxSlot slot) async {
    if (slot.primary || slot.path == null) return;
    final file = File(slot.path!);
    if (file.existsSync()) await file.delete();
    final secret = File(slot.path!.replaceFirst(RegExp(r'\.json$'), '.password'));
    if (secret.existsSync()) await secret.delete();
  }

  Future<void> _writeSecret(File file, String password) async {
    await ensureLayout();
    await file.parent.create(recursive: true);
    await file.writeAsString(password);
    if (!Platform.isWindows) {
      await Process.run('chmod', ['600', file.path]);
    }
  }

  /// Cartella `Contents` dell'app su macOS, cartella dell'eseguibile altrove.
  static Directory _appRoot() {
    final exe = File(Platform.resolvedExecutable);
    if (Platform.isMacOS) return exe.parent.parent; // MacOS/ -> Contents/
    return exe.parent;
  }

  /// Motore congelato dentro l'app, se il pacchetto lo porta con sé.
  ///
  /// macOS: `Contents/Resources/engine/neura-engine`.
  /// Windows e Linux: `engine/neura-engine(.exe)` accanto all'eseguibile.
  String? bundledEngine() {
    final root = _appRoot().path;
    final candidates = Platform.isMacOS
        ? ['$root/Resources/engine/neura-engine']
        : Platform.isWindows
            ? ['$root/engine/neura-engine.exe']
            : ['$root/engine/neura-engine'];
    for (final path in candidates) {
      if (File(path).existsSync()) return path;
    }
    return null;
  }

  /// Pesi del modello dentro l'app: `Contents/Resources/model` su macOS, `model/` altrove.
  String? bundledModelDir() {
    final root = _appRoot().path;
    final dir = Platform.isMacOS ? '$root/Resources/model' : '$root/model';
    return Directory(dir).existsSync() ? dir : null;
  }

  bool get bundled => bundledEngine() != null;

  /// Eseguibile e argomenti che precedono il comando `neuraec`.
  ({String executable, List<String> prefix, String workingDirectory}) launcher() {
    final engine = bundledEngine();
    if (engine != null) {
      return (executable: engine, prefix: const [], workingDirectory: home.path);
    }
    return (executable: resolvePython(), prefix: const ['-m', 'neuraec'], workingDirectory: resolveProject());
  }

  /// Variabili in più per il motore: dove stanno i pesi, se sono nell'app.
  Map<String, String> engineEnvironment() {
    final model = bundledModelDir();
    return {
      'PYTHONUNBUFFERED': '1',
      if (model != null) ...{
        'NEURA_MODEL_DIR': model,
        'HF_HUB_OFFLINE': '1',
        'TRANSFORMERS_OFFLINE': '1',
      },
    };
  }

  String resolvePython() {
    if (python != null && python!.isNotEmpty && File(python!).existsSync()) {
      return python!;
    }
    final fromEnv = Platform.environment['NEURA_PYTHON'];
    if (fromEnv != null && fromEnv.isNotEmpty && File(fromEnv).existsSync()) {
      return fromEnv;
    }
    final root = resolveProject();
    final posix = '$root/.venv/bin/python';
    final win = '$root/.venv/Scripts/python.exe';
    if (File(posix).existsSync()) return posix;
    if (File(win).existsSync()) return win;
    return Platform.isWindows ? 'python' : 'python3';
  }

  String resolveProject() {
    if (project != null && project!.isNotEmpty) return project!;
    final fromEnv = Platform.environment['NEURA_PROJECT'];
    if (fromEnv != null && fromEnv.isNotEmpty) return fromEnv;
    final candidates = [
      '${Directory.current.path}/../engine',
      '${Directory.current.path}/engine',
    ];
    for (final candidate in candidates) {
      if (Directory(candidate).existsSync() && File('$candidate/neura/cli.py').existsSync()) {
        return Directory(candidate).absolute.path;
      }
    }
    return Directory('${Directory.current.path}/../engine').absolute.path;
  }

  Process? _process;

  Future<void> stop() async {
    final process = _process;
    if (process == null) return;
    try {
      process.kill(ProcessSignal.sigterm);
    } catch (_) {}
  }

  Future<EngineResult> run(
    String command, {
    void Function(String line)? onLine,
    String? configPath,
    String? password,
    String? adapter,
    List<String> extra = const [],
  }) async {
    await ensureLayout();
    final secret = password ?? await loadPassword();
    final oauth = command == 'auth';
    final launch = launcher();
    final process = await Process.start(
      launch.executable,
      [
        ...launch.prefix,
        command,
        ...extra,
        '--config',
        configPath ?? configFile.path,
        if (!oauth) ...['--data', dataDir.path, '--encoder', 'auto'],
        if (!oauth && adapter != null) ...['--adapter', adapter],
      ],
      workingDirectory: launch.workingDirectory,
      environment: {
        ...Platform.environment,
        ...engineEnvironment(),
        if (secret.isNotEmpty) 'NEURA_IMAP_PASSWORD': secret,
      },
    );
    final out = StringBuffer();
    final err = StringBuffer();
    Future<void> collect(Stream<List<int>> stream, StringBuffer sink) {
      return stream.transform(utf8.decoder).transform(const LineSplitter()).forEach((line) {
        sink.writeln(line);
        onLine?.call(line);
      });
    }

    _process = process;
    try {
      await Future.wait([collect(process.stdout, out), collect(process.stderr, err)]);
    } catch (_) {
      // Il processo è stato interrotto.
    } finally {
      if (identical(_process, process)) _process = null;
    }
    final code = await process.exitCode;
    await _appendLog('$command exit=$code motore=${launch.executable}\n$out$err');
    return EngineResult(code, out.toString(), err.toString());
  }

  Future<void> _appendLog(String text) async {
    await ensureLayout();
    await logFile.writeAsString(
      '${DateTime.now().toIso8601String()} $text\n',
      mode: FileMode.append,
    );
  }
}
