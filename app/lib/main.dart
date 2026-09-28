import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';

import 'brand.dart';
import 'dashboard.dart';
import 'engine.dart';
import 'i18n/s.dart';
import 'mailbox_config.dart';
import 'menubar.dart';
import 'notify.dart';
import 'release.dart';
import 'updates.dart';

void main() {
  runApp(const NeuraApp());
}

class NeuraApp extends StatefulWidget {
  const NeuraApp({super.key, this.initialLocale, this.checkUpdates = true});

  /// When set, the language stays in memory. Used by tests.
  final Locale? initialLocale;

  /// Tests leave this off so the window does not call GitHub.
  final bool checkUpdates;

  @override
  State<NeuraApp> createState() => _NeuraAppState();
}

class _NeuraAppState extends State<NeuraApp> {
  late Locale _locale;

  @override
  void initState() {
    super.initState();
    _locale = widget.initialLocale ?? Locale(_savedOrSystem());
  }

  String _savedOrSystem() {
    try {
      final file = File('${NeuraEngine.defaultHome().path}/locale');
      if (file.existsSync()) {
        final saved = file.readAsStringSync().trim();
        if (S.codes.contains(saved)) return saved;
      }
    } catch (_) {}
    return S.pick(WidgetsBinding.instance.platformDispatcher.locale.languageCode);
  }

  Future<void> _setLocale(String code) async {
    final next = Locale(S.pick(code));
    setState(() => _locale = next);
    if (widget.initialLocale != null) return;
    try {
      final home = NeuraEngine.defaultHome();
      await home.create(recursive: true);
      await File('${home.path}/locale').writeAsString('${next.languageCode}\n');
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return AppText(
      s: S(_locale.languageCode),
      child: MaterialApp(
        title: 'NeuraEC',
        debugShowCheckedModeBanner: false,
        locale: _locale,
        theme: ThemeData(
          useMaterial3: true,
          scaffoldBackgroundColor: const Color(0xFFF5F7FC),
          colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF00A8D4)),
        ),
        home: NeuraHome(onLocale: _setLocale, checkUpdates: widget.checkUpdates),
      ),
    );
  }
}

class NeuraHome extends StatefulWidget {
  const NeuraHome({super.key, required this.onLocale, this.checkUpdates = true});

  final ValueChanged<String> onLocale;
  final bool checkUpdates;

  @override
  State<NeuraHome> createState() => _NeuraHomeState();
}

class _NeuraHomeState extends State<NeuraHome> {
  final _engine = NeuraEngine();
  final _host = TextEditingController();
  final _username = TextEditingController();
  final _password = TextEditingController();
  final _addresses = TextEditingController();
  final _prefix = TextEditingController(text: 'Neura-P');
  final _gmailId = TextEditingController();
  final _gmailSecret = TextEditingController();
  final _graphId = TextEditingController();
  bool _linked = false;
  int _n = 4;
  String _order = 'desc';
  String _provider = 'imap';
  String _placement = 'label';
  int _section = 0;
  int _selected = 0;
  List<MailboxSlot> _slots = [
    MailboxSlot(config: MailboxConfig.initial(), password: '', primary: true),
  ];
  bool _busy = false;
  bool _statsLoading = false;
  bool _halted = false;
  bool _failed = false;
  bool _serviceOn = false;
  bool _pass = false;
  bool _notifyOn = true;
  int _everyMinutes = 5;
  String? _status;
  String? _localeCode;
  final Set<String> _prepared = {};
  final List<String> _lines = [];
  final ScrollController _logScroll = ScrollController();
  NeuraStats? _stats;
  Timer? _timer;
  DateTime? _lastPredict;
  final DesktopNotifier _notifier = DesktopNotifier();
  bool _updateDot = false;
  bool _updateBusy = false;
  bool _updateDialog = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final code = AppText.of(context).code;
    final changed = _localeCode != null && _localeCode != code;
    _localeCode = code;
    if (changed && !_busy) _status = null;
    if (changed) _pushMenuStats();
  }

  @override
  void initState() {
    super.initState();
    _load();
    if (Platform.isMacOS || Platform.isWindows) {
      MenuBarBridge.listen((on) => _toggleService(on));
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    _logScroll.dispose();
    _host.dispose();
    _username.dispose();
    _password.dispose();
    _addresses.dispose();
    _prefix.dispose();
    _gmailId.dispose();
    _gmailSecret.dispose();
    _graphId.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final slots = await _engine.loadSlots();
    if (!mounted) return;
    final currentId = _slots[_selected].config.mailboxId;
    var index = slots.indexWhere((slot) => slot.config.mailboxId.isNotEmpty && slot.config.mailboxId == currentId);
    if (index < 0) index = 0;
    setState(() {
      _slots = slots;
      _selected = index;
      _applySlot(slots[index]);
    });
    await _refreshStats();
    await _refreshPrepared();
    await _loadOAuth();
    await _refreshLinked();
    final notify = await _engine.loadNotificationsOn();
    final every = await _engine.loadIntervalMinutes();
    if (!mounted) return;
    setState(() {
      _notifyOn = notify;
      _everyMinutes = every;
    });
    if (notify) {
      final allowed = await _notifier.ensurePermission();
      if (!mounted) return;
      if (!allowed) {
        setState(() => _notifyOn = false);
        await _engine.saveNotificationsOn(false);
      }
    }
    if (widget.checkUpdates) unawaited(_lookForUpdate(automatic: true));
  }

  Future<void> _lookForUpdate({required bool automatic}) async {
    if (!widget.checkUpdates || _updateBusy) return;
    _updateBusy = true;
    try {
      final store = UpdateStore(_engine.serviceFile);
      final skipped = await store.skippedVersion();
      if (automatic) {
        final last = await store.lastChecked();
        if (!shouldAutoCheck(last, DateTime.now())) {
          if (skipped != null && isNewerVersion(skipped, kReleaseVersion) && mounted) {
            setState(() => _updateDot = true);
          }
          return;
        }
      }
      final AvailableUpdate? update;
      try {
        update = await fetchLatestRelease(current: kReleaseVersion, platform: currentPlatform());
      } catch (_) {
        return;
      }
      await store.rememberCheck(DateTime.now());
      if (!mounted) return;
      if (update == null) {
        setState(() => _updateDot = false);
        if (!automatic) {
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(AppText.of(context).updateCurrent)));
        }
        return;
      }
      setState(() => _updateDot = true);
      if (automatic && !shouldPromptUpdate(update.version, skipped)) return;
      await _proposeUpdate(update);
    } finally {
      _updateBusy = false;
    }
  }

  Future<void> _proposeUpdate(AvailableUpdate update) async {
    if (!mounted || _updateDialog) return;
    _updateDialog = true;
    final choice = await showDialog<String>(
      context: context,
      builder: (context) {
        final s = AppText.of(context);
        return AlertDialog(
          title: Text(s.updateTitle(update.version)),
          content: Text(s.updateBody),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, 'later'), child: Text(s.updateLater)),
            FilledButton(onPressed: () => Navigator.pop(context, 'update'), child: Text(s.updateAction)),
          ],
        );
      },
    );
    _updateDialog = false;
    if (!mounted) return;
    if (choice != 'update') {
      await UpdateStore(_engine.serviceFile).rememberSkip(update.version);
      if (mounted) setState(() => _updateDot = true);
      return;
    }
    await _downloadUpdate(update);
  }

  Future<void> _downloadUpdate(AvailableUpdate update) async {
    if (!mounted) return;
    var cancelled = false;
    var dialogOpen = true;
    void Function(int received, int? total)? report;
    final closed = showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (context) {
        return _DownloadDialog(
          version: update.version,
          attach: (next) => report = next,
          onCancel: () {
            cancelled = true;
            if (!dialogOpen) return;
            dialogOpen = false;
            Navigator.pop(context);
          },
        );
      },
    );
    void closeDialog() {
      if (!mounted || !dialogOpen) return;
      dialogOpen = false;
      Navigator.pop(context);
    }

    try {
      final file = await downloadRelease(
        update,
        downloadsDirectory(),
        onProgress: (received, total) => report?.call(received, total),
        isCancelled: () => cancelled,
      );
      closeDialog();
      await closed;
      if (!cancelled) await revealDownload(file);
    } on DownloadCancelled {
      await closed;
    } catch (_) {
      closeDialog();
      await closed;
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(AppText.of(context).updateFailed)));
      }
    }
  }

  Future<void> _loadOAuth() async {
    final clients = await _engine.loadOAuth();
    if (!mounted) return;
    _gmailId.text = clients.gmailClientId;
    _gmailSecret.text = clients.gmailClientSecret;
    _graphId.text = clients.graphClientId;
  }

  Future<void> _refreshLinked() async {
    final slot = _slots[_selected];
    final linked = await _engine.hasToken(slot.path);
    if (mounted) setState(() => _linked = linked);
  }

  Future<void> _refreshPrepared() async {
    final ready = <String>{};
    for (final slot in _slots) {
      if (await _engine.isPrepared(slot)) ready.add(slot.config.mailboxId);
    }
    if (!mounted) return;
    setState(() {
      _prepared
        ..clear()
        ..addAll(ready);
    });
  }

  void _applySlot(MailboxSlot slot) {
    final config = slot.config;
    _host.text = config.host;
    _username.text = config.username;
    _password.text = slot.password;
    _addresses.text = config.ownAddresses.join(', ');
    _prefix.text = config.labelPrefix;
    _n = config.n;
    _order = config.order;
    _provider = config.provider;
    _placement = config.effectivePlacement;
    _refreshLinked();
  }

  MailboxConfig _configFromForm(MailboxSlot slot, {bool assignId = false}) {
    final addresses = _addresses.text
        .split(RegExp(r'[,\s]+'))
        .map((e) => e.trim())
        .where((e) => e.isNotEmpty)
        .toList();
    final username = _username.text.trim();
    var mailboxId = slot.config.mailboxId;
    var userId = slot.config.userId;
    if (assignId && mailboxId.isEmpty) {
      final taken = _slots.map((item) => item.config.mailboxId).where((id) => id.isNotEmpty);
      mailboxId = mailboxIdFor(username, taken);
      userId = mailboxId.startsWith('mb-') ? mailboxId.substring(3) : mailboxId;
    }
    return slot.config.copyWith(
      mailboxId: mailboxId,
      userId: userId,
      ownAddresses: addresses.isEmpty && username.isNotEmpty ? [username] : addresses,
      n: _n,
      order: _order,
      labelPrefix: _prefix.text.trim().isEmpty ? 'Neura-P' : _prefix.text.trim(),
      host: _provider == 'imap' ? _host.text.trim() : '',
      username: username,
      provider: _provider,
      placement: MailboxConfig.providerSupportsLabels(_provider) ? _placement : 'move',
      notifyLabels: slot.config.notifyLabels.where((label) => _folderNames().contains(label)).toList(),
    );
  }

  void _rememberForm() {
    if (_slots.isEmpty) return;
    final slot = _slots[_selected];
    _slots[_selected] = slot.copy(config: _configFromForm(slot), password: _password.text);
  }

  Future<bool> _persistSelected({bool quiet = false}) async {
    if (_provider == 'imap' && (_host.text.trim().isEmpty || _username.text.trim().isEmpty)) {
      if (!quiet && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(AppText.of(context).needHost)),
        );
      }
      return false;
    }
    if (_provider != 'imap' && _username.text.trim().isEmpty) {
      _username.text = _provider;
    }
    final slot = _slots[_selected];
    final config = _configFromForm(slot, assignId: !slot.primary && slot.config.mailboxId.isEmpty);
    final saved = await _engine.saveSlot(
      slot.copy(config: config, password: _password.text),
    );
    final slots = await _engine.loadSlots();
    if (!mounted) return true;
    final index = slots.indexWhere((item) => item.config.mailboxId == saved.config.mailboxId);
    setState(() {
      _slots = slots;
      _selected = index < 0 ? 0 : index;
      _applySlot(_slots[_selected]);
    });
    return true;
  }

  Future<void> _save() async {
    final ok = await _persistSelected();
    if (!ok || !mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(AppText.of(context).savedMailbox)),
    );
  }

  void _selectSlot(int index) {
    if (index == _selected) return;
    _rememberForm();
    setState(() {
      _selected = index;
      _applySlot(_slots[index]);
      _stats = null;
      _statsLoading = _slots[index].path != null;
    });
    if (_slots[index].path != null) _refreshStats();
  }

  void _addMailbox() {
    _rememberForm();
    final empty = _slots.indexWhere(
      (slot) => !slot.primary && slot.config.mailboxId.isEmpty && slot.config.username.trim().isEmpty,
    );
    if (empty >= 0) {
      _selectSlot(empty);
      return;
    }
    final base = _slots.first.config;
    final draft = MailboxConfig.draft().copyWith(
      n: base.n,
      order: base.order,
      notifyLabels: [mostUrgentFolder(base.n, base.order, 'imap', 'Neura-P')],
    );
    setState(() {
      _slots = [..._slots, MailboxSlot(config: draft, password: '', primary: false)];
      _selected = _slots.length - 1;
      _applySlot(_slots[_selected]);
    });
  }

  Future<void> _removeMailbox() async {
    final slot = _slots[_selected];
    if (slot.primary) return;
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) {
        final s = AppText.of(context);
        return AlertDialog(
          title: Text(s.removeTitle),
          content: Text(s.removeBody),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: Text(s.cancel)),
            FilledButton(onPressed: () => Navigator.pop(context, true), child: Text(s.remove)),
          ],
        );
      },
    );
    if (ok != true) return;
    if (slot.path != null) await _engine.deleteSlot(slot);
    if (!mounted) return;
    setState(() {
      _slots = [..._slots]..removeAt(_selected);
      if (_slots.isEmpty) {
        _slots = [MailboxSlot(config: MailboxConfig.initial(), password: '', primary: true)];
      }
      _selected = 0;
      _applySlot(_slots.first);
    });
  }

  Future<void> _resetStats() async {
    final slot = _slots[_selected];
    if (slot.config.mailboxId.isEmpty) return;
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) {
        final s = AppText.of(context);
        return AlertDialog(
          title: Text(s.resetStatsTitle),
          content: Text(s.resetStatsBody),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: Text(s.cancel)),
            FilledButton(onPressed: () => Navigator.pop(context, true), child: Text(s.reset)),
          ],
        );
      },
    );
    if (ok != true || !mounted) return;
    await _engine.resetStats(slot);
    if (!mounted) return;
    setState(() {
      _stats = null;
      _statsLoading = false;
    });
    final s = AppText.of(context);
    _log(s.statsCleared);
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(s.statsCleared)));
    await _refreshStats();
  }

  String _openingStatus(String command) {
    final s = AppText.of(context);
    switch (command) {
      case 'check':
        return s.checking;
      case 'init':
        return s.preparing;
      case 'predict':
        return s.searchingUnread;
      case 'cycle':
        return s.classifyingUnread;
      case 'nightly':
        return s.checkingMoves;
      default:
        return s.inProgress;
    }
  }

  void _log(String line) {
    final now = DateTime.now();
    final stamp = '${now.hour.toString().padLeft(2, '0')}:'
        '${now.minute.toString().padLeft(2, '0')}:'
        '${now.second.toString().padLeft(2, '0')}';
    _lines.add('$stamp   $line');
    if (_lines.length > 400) {
      _lines.removeRange(0, _lines.length - 400);
    }
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_logScroll.hasClients) return;
      _logScroll.jumpTo(_logScroll.position.maxScrollExtent);
    });
  }

  Future<void> _halt() async {
    _halted = true;
    await _engine.stop();
  }

  Future<void> _run(String command) async {
    final pass = command == 'predict' || command == 'cycle';
    setState(() {
      _busy = true;
      _pass = pass;
      _halted = false;
      _failed = false;
      _status = _openingStatus(command);
      _log('— ${_openingStatus(command)}');
    });
    final cycle = command == 'cycle';
    final saved = await _persistSelected(quiet: cycle);
    if (!saved && !cycle) {
      if (mounted) {
        setState(() {
          _busy = false;
          _pass = false;
        });
      }
      return;
    }
    final slot = _slots[_selected];
    final result = await _engine.run(
      command,
      configPath: cycle ? _engine.configFile.path : slot.path,
      password: cycle ? await _engine.loadPassword() : _password.text,
      onLine: (line) {
      if (!mounted || line.trim().isEmpty) return;
      final status = statusFromLine(line, AppText.of(context));
      setState(() {
        _log(line.trim());
        if (status != null) _status = status;
        if (lineIsFailure(line)) _failed = true;
      });
    });
    if (!mounted) return;
    setState(() {
      _busy = false;
      _pass = false;
      _failed = !_halted && (!result.ok || _failed);
      final s = AppText.of(context);
      if (_halted) {
        _status = s.interrupted;
      } else if (result.ok && !_failed) {
        _status = command == 'check' ? s.loginOk : s.done;
      } else if (_status == _openingStatus(command)) {
        _status = s.failed;
      }
      if (command == 'predict' || command == 'cycle') _lastPredict = DateTime.now();
    });
    if (command != 'check') await _refreshStats();
    if (command == 'predict' || command == 'cycle') await _announce();
    if (command == 'init' && result.ok) {
      await _refreshPrepared();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppText.of(context).trainingDone)),
      );
    }
  }

  Future<void> _prepareMailbox() async {
    final slot = _slots[_selected];
    final ready = _prepared.contains(slot.config.mailboxId);
    if (ready) {
      final ok = await showDialog<bool>(
        context: context,
        builder: (context) {
          final s = AppText.of(context);
          return AlertDialog(
            title: Text(s.retrainTitle),
            content: Text(s.retrainBody),
            actions: [
              TextButton(onPressed: () => Navigator.pop(context, false), child: Text(s.cancel)),
              FilledButton(onPressed: () => Navigator.pop(context, true), child: Text(s.trainAgain)),
            ],
          );
        },
      );
      if (ok != true || !mounted) return;
    }
    await _run('init');
  }

  Future<void> _refreshStats() async {
    final slot = _slots[_selected];
    if (slot.path == null || !File(slot.path!).existsSync()) {
      if (mounted) setState(() => _statsLoading = false);
      return;
    }
    final result = await _engine.run('stats', configPath: slot.path, password: slot.password);
    final parsed = NeuraStats.parse(result.stdoutText);
    if (!mounted) return;
    setState(() {
      _stats = parsed;
      _statsLoading = false;
    });
    await _pushMenuStats();
  }

  Future<void> _pushMenuStats() async {
    if (!mounted || _slots.isEmpty) return;
    if (!Platform.isMacOS && !Platform.isWindows) return;
    final s = AppText.of(context);
    await MenuBarBridge.update(
      serviceOn: _serviceOn,
      labels: {
        'menuActive': s.classificationOn,
        'menuPaused': s.classificationPaused,
        'menuStart': s.startClassification,
        'menuPause': s.pause,
        'menuOpen': s.openNeura,
        'menuQuit': s.quit,
      },
    );
  }

  Future<void> _setInterval(int minutes) async {
    if (!const [1, 5, 15].contains(minutes) || minutes == _everyMinutes) return;
    setState(() => _everyMinutes = minutes);
    await _engine.saveIntervalMinutes(minutes);
  }

  void _toggleService(bool on) {
    setState(() => _serviceOn = on);
    _timer?.cancel();
    if (on) {
      _timer = Timer.periodic(const Duration(seconds: 15), (_) => _tick());
    }
    _pushMenuStats();
  }

  Future<void> _announce() async {
    final batches = await drainNotifyQueue(_engine.home);
    if (!_notifyOn || !mounted) return;
    for (final batch in batches) {
      MailboxSlot? slot;
      for (final item in _slots) {
        if (item.config.mailboxId == batch.mailboxId) slot = item;
      }
      if (slot == null) continue;
      final s = AppText.of(context);
      _notifier.openAction = s.open;
      final notice = composeNotification(
        batch,
        slot.config.notifyLabels,
        countLine: s.folderCount,
      );
      if (notice == null) continue;
      await _notifier.show(notice);
      if (!mounted) return;
      setState(() {
        _log('${s.alertPrefix}: ${notice.title}');
        _status = '${s.alertPrefix}: ${notice.title}';
      });
    }
  }

  Future<void> _tick() async {
    await _announce();
    if (_busy) return;
    final now = DateTime.now();
    final due = _lastPredict == null || now.difference(_lastPredict!) >= Duration(minutes: _everyMinutes);
    if (due) await _run('cycle');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FC),
      body: Row(
        children: [
          _rail(),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(28, 22, 28, 12),
              child: Column(
                children: [
                  Expanded(
                    child: _section == 0
                        ? _dashboard()
                        : _section == 1
                            ? _mailbox()
                            : _service(),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _rail() {
    final s = AppText.of(context);
    final items = [
      (Icons.auto_awesome, s.navModel),
      (Icons.mail_outline, s.navMailboxes),
      (Icons.sync, s.navService),
    ];
    return Container(
      width: 104,
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0xFFD7F7FF), Color(0xFFE7DCFF)],
        ),
      ),
      child: SafeArea(
        child: Column(
          children: [
            if (Platform.isMacOS) const SizedBox(height: 28),
            const SizedBox(height: 18),
            const NeuraSphere(size: 46),
            const SizedBox(height: 28),
            for (var i = 0; i < items.length; i++)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 4, horizontal: 10),
                child: Material(
                  color: _section == i ? Colors.white : Colors.transparent,
                  borderRadius: BorderRadius.circular(16),
                  child: InkWell(
                    borderRadius: BorderRadius.circular(16),
                    onTap: () => setState(() => _section = i),
                    child: SizedBox(
                      width: double.infinity,
                      child: Padding(
                        padding: const EdgeInsets.symmetric(vertical: 10),
                        child: Column(
                          children: [
                            Icon(items[i].$1, color: const Color(0xFF12141A), size: 22),
                            const SizedBox(height: 4),
                            Text(
                              items[i].$2,
                              textAlign: TextAlign.center,
                              maxLines: 2,
                              style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: Color(0xFF12141A)),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            const Spacer(),
            _languageButton(s),
            const SizedBox(height: 8),
            _releaseMark(s),
            const SizedBox(height: 14),
          ],
        ),
      ),
    );
  }

  Widget _languageButton(S s) {
    return PopupMenuButton<String>(
      tooltip: s.language,
      initialValue: s.code,
      onSelected: widget.onLocale,
      itemBuilder: (context) => [
        for (final code in S.codes)
          PopupMenuItem(value: code, child: Text(S.names[code]!)),
      ],
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
        child: Text(
          s.code.toUpperCase(),
          style: const TextStyle(fontWeight: FontWeight.w800, color: Color(0xFF12141A), letterSpacing: 0.6),
        ),
      ),
    );
  }

  Widget _releaseMark(S s) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 10),
      child: Material(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        child: InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: widget.checkUpdates && !_updateBusy ? () => _lookForUpdate(automatic: false) : null,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 7),
            child: Column(
              children: [
                Text(
                  s.release.toUpperCase(),
                  style: const TextStyle(
                    color: Color(0xFF0099CC),
                    fontSize: 9,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 1.1,
                  ),
                ),
                const SizedBox(height: 2),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(
                      kReleaseVersion,
                      style: const TextStyle(
                        color: Color(0xFF12141A),
                        fontSize: 12,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    if (_updateDot) ...[
                      const SizedBox(width: 6),
                      const DecoratedBox(
                        decoration: BoxDecoration(color: Color(0xFF00D4FF), shape: BoxShape.circle),
                        child: SizedBox(width: 8, height: 8),
                      ),
                    ],
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _dashboard() {
    final slot = _slots[_selected];
    return NeuraDashboard(
      stats: _stats,
      mailboxes: [for (final item in _slots) item.titleFor(AppText.of(context))],
      selected: _selected,
      onSelect: _selectSlot,
      order: slot.config.order,
      n: slot.config.n,
      prefix: slot.config.labelPrefix,
      provider: slot.config.provider,
      busy: _busy,
      activity: _status ?? '',
      loading: _statsLoading,
      serviceOn: _serviceOn,
      live: _pass,
      onRefresh: _refreshStats,
      onClassify: () => _run('predict'),
      onToggleService: () => _toggleService(!_serviceOn),
      onStop: _halt,
      intervalMinutes: _everyMinutes,
      onInterval: _setInterval,
    );
  }

  Widget _mailbox() {
    final s = AppText.of(context);
    final slot = _slots[_selected];
    return Padding(
      padding: const EdgeInsets.fromLTRB(8, 8, 8, 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: Text(
                s.mailboxesTitle,
                style: const TextStyle(fontSize: 36, fontWeight: FontWeight.w800, color: Color(0xFF12141A), height: 1),
              ),
            ),
            const Padding(
              padding: EdgeInsets.only(top: 6, left: 16),
              child: IanustecLogo(height: 22),
            ),
          ],
        ),
        const SizedBox(height: 6),
        Text(
          s.mailboxesSubtitle,
          style: const TextStyle(color: Color(0xFF5C6478), fontSize: 15),
        ),
        const SizedBox(height: 18),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (var i = 0; i < _slots.length; i++) _slotTile(i),
            _addTile(),
          ],
        ),
        const SizedBox(height: 16),
        Expanded(
          child: ListView(
            padding: const EdgeInsets.only(bottom: 28),
            children: [
              _panel(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(s.account, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: Color(0xFF12141A))),
                    const SizedBox(height: 4),
                    Text(
                      slot.primary ? s.accountWorking : s.accountSave,
                      style: const TextStyle(color: Color(0xFF5C6478)),
                    ),
                    const SizedBox(height: 18),
                    Text(s.accountType, style: const TextStyle(fontWeight: FontWeight.w700, color: Color(0xFF12141A))),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        _choice('IMAP', _provider == 'imap', () => setState(() => _provider = 'imap')),
                        _choice('Gmail', _provider == 'gmail', () => setState(() => _provider = 'gmail')),
                        _choice('Microsoft', _provider == 'graph', () => setState(() => _provider = 'graph')),
                      ],
                    ),
                    const SizedBox(height: 16),
                    if (_provider == 'imap') ...[
                      TextField(controller: _host, decoration: _field(s.hostImap)),
                      const SizedBox(height: 12),
                      TextField(controller: _username, decoration: _field(s.user)),
                      const SizedBox(height: 12),
                      TextField(controller: _password, obscureText: true, decoration: _field(s.password)),
                    ] else ...[
                      _oauthGuide(),
                      const SizedBox(height: 12),
                      TextField(
                        controller: _username,
                        decoration: _field(s.user, s.userHint),
                      ),
                    ],
                    const SizedBox(height: 12),
                    TextField(
                      controller: _addresses,
                      decoration: _field(s.otherAddresses, s.otherAddressesHint),
                    ),
                    const SizedBox(height: 16),
                    _serviceButton(s.tryLogin, () => _run('check'), filled: false),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              _panel(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(s.priority, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: Color(0xFF12141A))),
                    const SizedBox(height: 4),
                    Text(
                      _provider == 'graph'
                          ? s.graphPriority
                          : _provider == 'gmail'
                              ? s.gmailPriority
                              : s.imapPriority,
                      style: const TextStyle(color: Color(0xFF5C6478)),
                    ),
                    const SizedBox(height: 16),
                    Text(s.whereMailGoes, style: const TextStyle(fontWeight: FontWeight.w700, color: Color(0xFF12141A))),
                    const SizedBox(height: 8),
                    if (MailboxConfig.providerSupportsLabels(_provider))
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          _choice(s.labelStays, _placement == 'label', () => setState(() => _placement = 'label')),
                          _choice(s.moveToFolder, _placement == 'move', () => setState(() => _placement = 'move')),
                        ],
                      )
                    else
                      Text(
                        s.foldersOnly,
                        style: const TextStyle(color: Color(0xFF5C6478)),
                      ),
                    if (MailboxConfig.providerSupportsLabels(_provider)) ...[
                      const SizedBox(height: 6),
                      Text(
                        _placement == 'label' ? s.labelExplain : s.moveExplain,
                        style: const TextStyle(color: Color(0xFF5C6478)),
                      ),
                    ],
                    const SizedBox(height: 16),
                    TextField(
                      controller: _prefix,
                      decoration: _field(
                        MailboxConfig.providerSupportsLabels(_provider) && _placement == 'label'
                            ? s.labelNames
                            : s.folderNames,
                      ),
                      onChanged: (_) => setState(() {}),
                    ),
                    const SizedBox(height: 16),
                    Text(s.howMany, style: const TextStyle(fontWeight: FontWeight.w700, color: Color(0xFF12141A))),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        for (var n = 3; n <= 10; n++)
                          _choice('$n', _n == n, () => setState(() => _n = n)),
                      ],
                    ),
                    const SizedBox(height: 16),
                    Text(s.whichUrgent, style: const TextStyle(fontWeight: FontWeight.w700, color: Color(0xFF12141A))),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        _choice(s.theFirst, _order == 'desc', () => setState(() => _order = 'desc')),
                        _choice(s.theLast, _order == 'asc', () => setState(() => _order = 'asc')),
                      ],
                    ),
                    const SizedBox(height: 16),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        for (final name in _folderNames())
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                            decoration: BoxDecoration(
                              color: name == mostUrgentFolder(_n, _order, _provider, _prefix.text.trim().isEmpty ? 'Neura-P' : _prefix.text.trim())
                                  ? const Color(0xFF12141A)
                                  : const Color(0xFFE8F8FF),
                              borderRadius: BorderRadius.circular(999),
                            ),
                            child: Text(
                              folderLeaf(name),
                              style: TextStyle(
                                fontWeight: FontWeight.w700,
                                color: name == mostUrgentFolder(_n, _order, _provider, _prefix.text.trim().isEmpty ? 'Neura-P' : _prefix.text.trim())
                                    ? Colors.white
                                    : const Color(0xFF0099CC),
                              ),
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text(s.darkIsUrgent, style: const TextStyle(color: Color(0xFF5C6478))),
                    const SizedBox(height: 14),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: OutlinedButton(
                        onPressed: _busy || slot.config.mailboxId.isEmpty ? null : _resetStats,
                        style: OutlinedButton.styleFrom(
                          foregroundColor: const Color(0xFF12141A),
                          side: const BorderSide(color: Color(0xFFD5DCE8)),
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                        ),
                        child: Text(s.resetStats),
                      ),
                    ),
                    const SizedBox(height: 16),
                    Row(
                      children: [
                        FilledButton(
                          onPressed: _busy ? null : _save,
                          style: FilledButton.styleFrom(
                            backgroundColor: const Color(0xFF12141A),
                            foregroundColor: Colors.white,
                            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                          ),
                          child: Text(s.save),
                        ),
                        if (!slot.primary) ...[
                          const SizedBox(width: 12),
                          TextButton(onPressed: _busy ? null : _removeMailbox, child: Text(s.removeMailbox)),
                        ],
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              _panel(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _prepared.contains(slot.config.mailboxId) ? s.trained : s.training,
                      style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: Color(0xFF12141A)),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      _prepared.contains(slot.config.mailboxId) ? s.trainedBody : s.trainingBody,
                      style: const TextStyle(color: Color(0xFF5C6478)),
                    ),
                    const SizedBox(height: 16),
                    if (!_prepared.contains(slot.config.mailboxId))
                      FilledButton(
                        onPressed: _busy ? null : _prepareMailbox,
                        style: FilledButton.styleFrom(
                          backgroundColor: const Color(0xFF12141A),
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                        ),
                        child: Text(s.startTraining),
                      )
                    else
                      TextButton(onPressed: _busy ? null : _prepareMailbox, child: Text(s.trainAgain)),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              _panel(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(s.alerts, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: Color(0xFF12141A))),
                    const SizedBox(height: 4),
                    Text(
                      s.alertsBody,
                      style: const TextStyle(color: Color(0xFF5C6478)),
                    ),
                    SwitchListTile(
                      contentPadding: EdgeInsets.zero,
                      title: Text(s.desktopNotifications, style: const TextStyle(fontWeight: FontWeight.w700)),
                      subtitle: Text(
                        s.notificationsScope,
                        style: const TextStyle(color: Color(0xFF5C6478)),
                      ),
                      value: _notifyOn,
                      onChanged: _busy ? null : _setNotifications,
                    ),
                    if (slot.config.mailboxId.isNotEmpty) _notifyMailbox(_selected, showAccount: false),
                  ],
                ),
              ),
            ],
          ),
        ),
        ],
      ),
    );
  }

  Widget _slotTile(int index) {
    final slot = _slots[index];
    final selected = index == _selected;
    return Material(
      color: selected ? const Color(0xFF12141A) : Colors.white,
      borderRadius: BorderRadius.circular(999),
      child: InkWell(
        borderRadius: BorderRadius.circular(999),
        onTap: _busy ? null : () => _selectSlot(index),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          child: Text(
            slot.titleFor(AppText.of(context)),
            style: TextStyle(fontWeight: FontWeight.w700, color: selected ? Colors.white : const Color(0xFF12141A)),
          ),
        ),
      ),
    );
  }

  Widget _addTile() {
    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(999),
      child: InkWell(
        borderRadius: BorderRadius.circular(999),
        onTap: _busy ? null : _addMailbox,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.add, size: 18, color: Color(0xFF0099CC)),
              const SizedBox(width: 6),
              Text(AppText.of(context).addMailbox, style: const TextStyle(fontWeight: FontWeight.w700, color: Color(0xFF0099CC))),
            ],
          ),
        ),
      ),
    );
  }

  Widget _choice(String label, bool selected, VoidCallback onTap) {
    return Material(
      color: selected ? const Color(0xFF12141A) : const Color(0xFFF5F7FC),
      borderRadius: BorderRadius.circular(999),
      child: InkWell(
        borderRadius: BorderRadius.circular(999),
        onTap: _busy ? null : onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          child: Text(
            label,
            style: TextStyle(fontWeight: FontWeight.w700, color: selected ? Colors.white : const Color(0xFF12141A)),
          ),
        ),
      ),
    );
  }

  InputDecoration _field(String label, [String? helper]) {
    const radius = BorderRadius.all(Radius.circular(14));
    return InputDecoration(
      labelText: label,
      helperText: helper,
      filled: true,
      fillColor: const Color(0xFFF5F7FC),
      border: const OutlineInputBorder(borderRadius: radius, borderSide: BorderSide.none),
      enabledBorder: const OutlineInputBorder(borderRadius: radius, borderSide: BorderSide(color: Color(0xFFE4E8F2))),
      focusedBorder: const OutlineInputBorder(borderRadius: radius, borderSide: BorderSide(color: Color(0xFF00D4FF), width: 1.6)),
    );
  }

  Widget _notifyMailbox(int index, {bool showAccount = true}) {
    final s = AppText.of(context);
    final slot = _slots[index];
    final config = slot.config;
    final folders = [
      for (final label in priorityLabels(config.n, config.provider, config.labelPrefix))
        label['provider_label'].toString(),
    ];
    final urgent = mostUrgentFolder(config.n, config.order, config.provider, config.labelPrefix);
    return Padding(
      padding: EdgeInsets.only(top: showAccount ? 8 : 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (showAccount)
            Text(slot.titleFor(s), style: const TextStyle(fontWeight: FontWeight.w700, color: Color(0xFF12141A))),
          for (final folder in folders)
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(folderLeaf(folder)),
              subtitle: folder == urgent
                  ? Text(s.mostUrgent, style: const TextStyle(color: Color(0xFF5C6478)))
                  : null,
              value: config.notifyLabels.contains(folder),
              onChanged: _busy || !_notifyOn ? null : (on) => _toggleNotifyLabel(index, folder, on),
            ),
          if (config.notifyLabels.isEmpty)
            Text(
              s.noPriorityOn,
              style: const TextStyle(color: Color(0xFF5C6478)),
            ),
        ],
      ),
    );
  }

  Future<void> _setNotifications(bool on) async {
    if (!on) {
      setState(() => _notifyOn = false);
      await _engine.saveNotificationsOn(false);
      return;
    }
    final allowed = await _notifier.ensurePermission();
    if (!mounted) return;
    if (!allowed) {
      setState(() => _notifyOn = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppText.of(context).macDenied)),
      );
      await _engine.saveNotificationsOn(false);
      return;
    }
    setState(() => _notifyOn = true);
    await _engine.saveNotificationsOn(true);
    if (!mounted) return;
    final s = AppText.of(context);
    final account = _slots[_selected].titleFor(s);
    _notifier.openAction = s.open;
    await _notifier.show(DesktopNotice('NeuraEC', s.notificationsActive(account)));
  }

  Future<void> _toggleNotifyLabel(int index, String folder, bool on) async {
    final slot = _slots[index];
    final labels = [...slot.config.notifyLabels];
    if (on) {
      if (!labels.contains(folder)) labels.add(folder);
    } else {
      labels.remove(folder);
    }
    final saved = await _engine.saveSlot(slot.copy(config: slot.config.copyWith(notifyLabels: labels)));
    if (!mounted) return;
    setState(() => _slots[index] = saved.copy(password: slot.password));
  }

  Widget _panel({required Widget child}) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(24),
        boxShadow: const [BoxShadow(color: Color(0x120B3040), blurRadius: 24, offset: Offset(0, 10))],
      ),
      child: child,
    );
  }

  Widget _service() {
    final s = AppText.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(8, 8, 8, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Text(
                  s.serviceTitle,
                  style: const TextStyle(fontSize: 36, fontWeight: FontWeight.w800, color: Color(0xFF12141A), height: 1),
                ),
              ),
              const Padding(
                padding: EdgeInsets.only(top: 6, left: 16),
                child: IanustecLogo(height: 22),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            s.serviceSubtitle,
            style: const TextStyle(color: Color(0xFF5C6478), fontSize: 15),
          ),
          const SizedBox(height: 18),
          Expanded(
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.fromLTRB(20, 20, 20, 14),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(24),
                boxShadow: const [BoxShadow(color: Color(0x120B3040), blurRadius: 24, offset: Offset(0, 10))],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(s.log, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: Color(0xFF12141A))),
                      ),
                      TextButton(
                        onPressed: _lines.isEmpty ? null : () => setState(_lines.clear),
                        style: TextButton.styleFrom(foregroundColor: const Color(0xFF5C6478)),
                        child: Text(s.clear),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Expanded(child: _logBox()),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _serviceButton(String label, VoidCallback onPressed, {bool filled = false}) {
    final shape = RoundedRectangleBorder(borderRadius: BorderRadius.circular(14));
    if (filled) {
      return FilledButton(
        onPressed: _busy ? null : onPressed,
        style: FilledButton.styleFrom(
          backgroundColor: const Color(0xFF12141A),
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
          shape: shape,
        ),
        child: Text(label),
      );
    }
    return FilledButton.tonal(
      onPressed: _busy ? null : onPressed,
      style: FilledButton.styleFrom(
        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
        shape: shape,
      ),
      child: Text(label),
    );
  }

  Widget _logBox() {
    if (_lines.isEmpty) {
      return Center(
        child: Text(
          AppText.of(context).logEmpty,
          style: const TextStyle(color: Color(0xFF5C6478)),
        ),
      );
    }
    return ListView.builder(
      controller: _logScroll,
      itemCount: _lines.length,
      itemBuilder: (context, index) {
        final line = _lines[index];
        final marker = line.contains('— ');
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 3),
          child: Text(
            line,
            style: TextStyle(
              fontFamily: 'Menlo',
              fontSize: 13,
              height: 1.35,
              fontWeight: marker ? FontWeight.w700 : FontWeight.w400,
              color: marker ? const Color(0xFF12141A) : const Color(0xFF3A4154),
            ),
          ),
        );
      },
    );
  }

  Widget _oauthGuide() {
    final s = AppText.of(context);
    final gmail = _provider == 'gmail';
    final ready = gmail ? _gmailId.text.trim().isNotEmpty && _gmailSecret.text.trim().isNotEmpty : _graphId.text.trim().isNotEmpty;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFFE7FBFF), Color(0xFFF4E9FF)],
        ),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            gmail ? s.gmailOnce : s.microsoftOnce,
            style: const TextStyle(fontWeight: FontWeight.w800, color: Color(0xFF12141A)),
          ),
          const SizedBox(height: 8),
          Text(_oauthSteps(), style: const TextStyle(color: Color(0xFF12141A), height: 1.4)),
          const SizedBox(height: 12),
          if (gmail) ...[
            TextField(controller: _gmailId, decoration: _field(s.googleClientId)),
            const SizedBox(height: 8),
            TextField(controller: _gmailSecret, obscureText: true, decoration: _field(s.googleSecret)),
          ] else
            TextField(controller: _graphId, decoration: _field(s.microsoftAppId)),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              FilledButton(
                onPressed: _busy ? null : _saveOAuth,
                style: FilledButton.styleFrom(
                  backgroundColor: const Color(0xFF12141A),
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                ),
                child: Text(s.saveLink),
              ),
              FilledButton.tonal(
                onPressed: _busy || !ready ? null : _connectAccount,
                style: FilledButton.styleFrom(shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14))),
                child: Text(_linked ? s.relink : s.link),
              ),
            ],
          ),
          if (_linked) ...[
            const SizedBox(height: 8),
            Text(s.accountLinked, style: const TextStyle(color: Color(0xFF5C6478))),
          ],
        ],
      ),
    );
  }

  String _oauthSteps() {
    final s = AppText.of(context);
    return _provider == 'gmail' ? s.gmailSteps : s.microsoftSteps;
  }

  Future<void> _saveOAuth() async {
    await _engine.saveOAuth(
      OAuthClients(
        gmailClientId: _gmailId.text,
        gmailClientSecret: _gmailSecret.text,
        graphClientId: _graphId.text,
      ),
    );
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(AppText.of(context).oauthSaved)),
    );
    setState(() {});
  }

  Future<void> _connectAccount() async {
    final ok = await _persistSelected();
    if (!ok || !mounted) return;
    final path = _slots[_selected].path;
    if (path == null) return;
    final s = AppText.of(context);
    setState(() {
      _busy = true;
      _failed = false;
      _status = s.waitingBrowser;
      _log('— ${_provider == 'gmail' ? s.connectingGmail : s.connectingMicrosoft}');
    });
    final result = await _engine.run(
      'auth',
      configPath: path,
      extra: [_provider],
      password: '',
      onLine: (line) {
        if (!mounted || line.trim().isEmpty) return;
        setState(() {
          _log(line.trim());
          _status = line.trim();
        });
      },
    );
    if (!mounted) return;
    final match = RegExp(r'(?:connected|collegato):\s*(\S+)').firstMatch(result.stdoutText);
    if (result.ok && match != null && match.group(1) != 'account') {
      final email = match.group(1)!;
      _username.text = email;
      _addresses.text = email;
      await _persistSelected(quiet: true);
    }
    if (!mounted) return;
    setState(() {
      _busy = false;
      _failed = !result.ok;
      _status = result.ok ? AppText.of(context).linked : AppText.of(context).linkFailed;
      _linked = result.ok;
    });
  }

  List<String> _folderNames() {
    return [
      for (final label in priorityLabels(_n, _provider, _prefix.text)) label['provider_label'].toString(),
    ];
  }

}

class _DownloadDialog extends StatefulWidget {
  const _DownloadDialog({required this.version, required this.attach, required this.onCancel});

  final String version;
  final void Function(void Function(int received, int? total) report) attach;
  final VoidCallback onCancel;

  @override
  State<_DownloadDialog> createState() => _DownloadDialogState();
}

class _DownloadDialogState extends State<_DownloadDialog> {
  int _received = 0;
  int? _total;

  @override
  void initState() {
    super.initState();
    widget.attach((received, total) {
      if (!mounted) return;
      setState(() {
        _received = received;
        _total = total;
      });
    });
  }

  @override
  Widget build(BuildContext context) {
    final s = AppText.of(context);
    final known = _total != null && _total! > 0;
    return AlertDialog(
      title: Text(s.updateDownload(widget.version)),
      content: LinearProgressIndicator(value: known ? _received / _total! : null),
      actions: [
        TextButton(onPressed: widget.onCancel, child: Text(s.cancel)),
      ],
    );
  }
}
