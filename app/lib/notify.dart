import 'dart:convert';
import 'dart:io';

import 'package:flutter_local_notifications/flutter_local_notifications.dart';

import 'mailbox_config.dart';
import 'menubar.dart';

/// Una mail appena etichettata, come la scrive il motore in ~/.neura/notify.
class NotifyItem {
  const NotifyItem({
    required this.rank,
    required this.label,
    required this.fromAddr,
    required this.subject,
    required this.snippet,
  });

  final int rank;
  final String label;
  final String fromAddr;
  final String subject;
  final String snippet;

  factory NotifyItem.fromJson(Map<String, dynamic> json) {
    return NotifyItem(
      rank: (json['rank'] as num?)?.toInt() ?? 0,
      label: (json['label'] ?? '').toString(),
      fromAddr: (json['from_addr'] ?? '').toString(),
      subject: (json['subject'] ?? '').toString(),
      snippet: (json['snippet'] ?? '').toString(),
    );
  }
}

/// Un passaggio del motore, per una casella.
class NotifyBatch {
  const NotifyBatch({
    required this.mailboxId,
    required this.account,
    required this.items,
  });

  final String mailboxId;
  final String account;
  final List<NotifyItem> items;

  factory NotifyBatch.fromJson(Map<String, dynamic> json) {
    final raw = json['items'];
    final items = raw is List
        ? [
            for (final item in raw)
              if (item is Map) NotifyItem.fromJson(Map<String, dynamic>.from(item)),
          ]
        : <NotifyItem>[];
    return NotifyBatch(
      mailboxId: (json['mailbox_id'] ?? '').toString(),
      account: (json['account'] ?? '').toString(),
      items: items,
    );
  }

  NotifyBatch merge(NotifyBatch other) {
    return NotifyBatch(
      mailboxId: mailboxId,
      account: account.isNotEmpty ? account : other.account,
      items: [...items, ...other.items],
    );
  }
}

class DesktopNotice {
  const DesktopNotice(this.title, this.body);

  final String title;
  final String body;
}

/// Regola BeC: una mail da sola porta oggetto e snippet; più mail, un conteggio per cartella.
DesktopNotice? composeNotification(
  NotifyBatch batch,
  List<String> notifyLabels, {
  String Function(String folder, int count)? countLine,
}) {
  final wanted = notifyLabels.toSet();
  final kept = batch.items.where((item) => wanted.contains(item.label)).toList();
  if (kept.isEmpty) return null;
  if (kept.length == 1) {
    final item = kept.single;
    final lines = [item.subject, item.snippet].where((line) => line.trim().isNotEmpty);
    return DesktopNotice('${folderLeaf(item.label)} · ${batch.account}', lines.join('\n'));
  }
  final counts = <String, int>{};
  final order = <String>[];
  final sorted = [...kept]..sort((a, b) => a.rank.compareTo(b.rank));
  for (final item in sorted) {
    counts.update(item.label, (n) => n + 1, ifAbsent: () {
      order.add(item.label);
      return 1;
    });
  }
  final body = [
    for (final label in order)
      countLine?.call(folderLeaf(label), counts[label]!) ?? '· ${folderLeaf(label)}: ${counts[label]} email',
  ].join('\n');
  return DesktopNotice(batch.account, body);
}

/// Legge e cancella i file della coda, raggruppati per casella.
Future<List<NotifyBatch>> drainNotifyQueue(Directory home) async {
  final dir = Directory('${home.path}/notify');
  if (!dir.existsSync()) return const [];
  final files = dir
      .listSync()
      .whereType<File>()
      .where((file) => file.path.endsWith('.json'))
      .toList()
    ..sort((a, b) => a.path.compareTo(b.path));
  final byMailbox = <String, NotifyBatch>{};
  for (final file in files) {
    try {
      final decoded = jsonDecode(await file.readAsString());
      if (decoded is Map) {
        final batch = NotifyBatch.fromJson(Map<String, dynamic>.from(decoded));
        final previous = byMailbox[batch.mailboxId];
        byMailbox[batch.mailboxId] = previous == null ? batch : previous.merge(batch);
      }
    } catch (_) {}
    try {
      await file.delete();
    } catch (_) {}
  }
  return byMailbox.values.toList();
}

/// Notifiche locali. Su macOS il clic riapre la finestra.
class DesktopNotifier {
  DesktopNotifier() : _plugin = FlutterLocalNotificationsPlugin();

  final FlutterLocalNotificationsPlugin _plugin;
  bool _ready = false;
  int _seq = 0;
  String openAction = 'Apri';

  /// Chiede al sistema il permesso di mostrare avvisi. Su macOS apre il dialogo,
  /// una sola volta: se l'utente ha già risposto, restituisce la scelta fatta.
  Future<bool> ensurePermission() async {
    try {
      await _ensureReady();
      if (Platform.isMacOS) {
        final mac = _plugin.resolvePlatformSpecificImplementation<MacOSFlutterLocalNotificationsPlugin>();
        final granted = await mac?.requestPermissions(alert: true, sound: true);
        return granted ?? false;
      }
      if (Platform.isWindows || Platform.isLinux) return true;
      return false;
    } catch (_) {
      return false;
    }
  }

  Future<void> _ensureReady() async {
    if (_ready) return;
    await _plugin.initialize(
      InitializationSettings(
        macOS: DarwinInitializationSettings(
          requestAlertPermission: false,
          requestSoundPermission: false,
          requestBadgePermission: false,
        ),
        windows: WindowsInitializationSettings(
          appName: 'NeuraEC',
          appUserModelId: 'it.bentho.neuraApp',
          guid: '8f3c1a20-6b4e-4d7a-9c15-2e6f0a8b4d31',
        ),
        linux: LinuxInitializationSettings(defaultActionName: openAction),
      ),
      onDidReceiveNotificationResponse: _opened,
    );
    _ready = true;
  }

  Future<void> show(DesktopNotice notice) async {
    try {
      await _ensureReady();
      _seq = (_seq + 1) % 100000;
      await _plugin.show(
        _seq,
        notice.title,
        notice.body,
        const NotificationDetails(
          macOS: DarwinNotificationDetails(),
          windows: WindowsNotificationDetails(),
          linux: LinuxNotificationDetails(),
        ),
      );
    } catch (_) {
      // Senza permesso o senza plugin la classifica non si ferma.
    }
  }

  static void _opened(NotificationResponse response) {
    if (Platform.isMacOS) MenuBarBridge.show();
  }
}
