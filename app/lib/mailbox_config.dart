import 'dart:convert';

import 'i18n/s.dart';

/// Configurazione casella scritta in mailbox.json. La password non entra qui.
class MailboxConfig {
  MailboxConfig({
    required this.mailboxId,
    required this.userId,
    required this.ownAddresses,
    required this.n,
    required this.order,
    required this.provider,
    required this.host,
    required this.username,
    required this.port,
    required this.tls,
    this.labelPrefix = 'Neura-P',
    this.notifyLabels = const [],
    this.placement = '',
  });

  final String mailboxId;
  final String userId;
  final List<String> ownAddresses;
  final int n;
  final String order;
  final String provider;
  final String host;
  final String username;
  final int port;
  final String tls;
  final String labelPrefix;
  final List<String> notifyLabels;

  /// Dove finisce la mail classificata: 'move' nella cartella, 'label' resta in Arrivo
  /// con l'etichetta. Vuoto = default del provider.
  final String placement;

  /// IMAP ha solo cartelle. Gmail e Microsoft sanno anche etichettare.
  static bool providerSupportsLabels(String provider) => provider == 'gmail' || provider == 'graph';

  String get effectivePlacement {
    if (!providerSupportsLabels(provider)) return 'move';
    return placement == 'move' ? 'move' : 'label';
  }

  factory MailboxConfig.initial() {
    return MailboxConfig(
      mailboxId: 'mb-locale',
      userId: 'me',
      ownAddresses: const [],
      n: 4,
      order: 'desc',
      provider: 'imap',
      host: '',
      username: '',
      port: 993,
      tls: 'ssl',
      labelPrefix: 'Neura-P',
      notifyLabels: [mostUrgentFolder(4, 'desc', 'imap', 'Neura-P')],
    );
  }

  factory MailboxConfig.fromJson(Map<String, dynamic> json) {
    final addresses = (json['own_addresses'] as List<dynamic>? ?? const [])
        .map((e) => e.toString())
        .toList();
    final n = (json['N'] as num?)?.toInt() ?? 4;
    final order = (json['order'] ?? 'desc').toString();
    final provider = (json['provider'] ?? 'imap').toString();
    final prefix = (json['label_prefix'] ?? _inferPrefix(json['labels']))?.toString() ?? 'Neura-P';
    final stored = json['notify_labels'];
    final notify = stored is List
        ? stored.map((e) => e.toString()).where((e) => e.isNotEmpty).toList()
        : [mostUrgentFolder(n, order, provider, prefix)];
    return MailboxConfig(
      mailboxId: (json['mailbox_id'] ?? 'mb-locale').toString(),
      userId: (json['user_id'] ?? 'me').toString(),
      ownAddresses: addresses,
      n: n,
      order: order,
      provider: provider,
      host: (json['host'] ?? '').toString(),
      username: (json['username'] ?? '').toString(),
      port: (json['port'] as num?)?.toInt() ?? 993,
      tls: (json['tls'] ?? 'ssl').toString(),
      labelPrefix: prefix,
      notifyLabels: notify,
      placement: (json['placement'] ?? '').toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'mailbox_id': mailboxId,
      'user_id': userId,
      'own_addresses': ownAddresses,
      'N': n,
      'order': order,
      'provider': provider,
      'host': host,
      'username': username,
      'port': port,
      'tls': tls,
      'label_prefix': labelPrefix,
      'notify_labels': notifyLabels,
      'placement': effectivePlacement,
      'profile': {'fig': <String>[], 'fun': <String>[], 'set': <String>[]},
      'labels': priorityLabels(n, provider, labelPrefix),
    };
  }

  String encode() => const JsonEncoder.withIndent('  ').convert(toJson());

  MailboxConfig copyWith({
    String? mailboxId,
    String? userId,
    List<String>? ownAddresses,
    int? n,
    String? order,
    String? provider,
    String? host,
    String? username,
    int? port,
    String? tls,
    String? labelPrefix,
    List<String>? notifyLabels,
    String? placement,
  }) {
    return MailboxConfig(
      mailboxId: mailboxId ?? this.mailboxId,
      userId: userId ?? this.userId,
      ownAddresses: ownAddresses ?? this.ownAddresses,
      n: n ?? this.n,
      order: order ?? this.order,
      provider: provider ?? this.provider,
      host: host ?? this.host,
      username: username ?? this.username,
      port: port ?? this.port,
      tls: tls ?? this.tls,
      labelPrefix: labelPrefix ?? this.labelPrefix,
      notifyLabels: notifyLabels ?? this.notifyLabels,
      placement: placement ?? this.placement,
    );
  }

  factory MailboxConfig.draft() {
    return MailboxConfig(
      mailboxId: '',
      userId: '',
      ownAddresses: const [],
      n: 4,
      order: 'asc',
      provider: 'imap',
      host: '',
      username: '',
      port: 993,
      tls: 'ssl',
      labelPrefix: 'Neura-P',
      notifyLabels: [mostUrgentFolder(4, 'asc', 'imap', 'Neura-P')],
    );
  }
}

/// Una casella in elenco. La principale è mailbox.json; le altre stanno in mailboxes/.
class MailboxSlot {
  const MailboxSlot({
    required this.config,
    required this.password,
    required this.primary,
    this.path,
  });

  final MailboxConfig config;
  final String password;
  final bool primary;
  final String? path;

  String titleFor(S s) {
    if (config.username.trim().isEmpty) return s.newMailbox;
    return config.username.trim();
  }

  MailboxSlot copy({MailboxConfig? config, String? password, String? path, bool? primary}) {
    return MailboxSlot(
      config: config ?? this.config,
      password: password ?? this.password,
      primary: primary ?? this.primary,
      path: path ?? this.path,
    );
  }
}

/// Id stabile per una casella aggiunta. Non riusa gli id già presi.
String mailboxIdFor(String username, Iterable<String> taken) {
  final local = username.split('@').first.toLowerCase();
  var slug = local.replaceAll(RegExp(r'[^a-z0-9]+'), '-').replaceAll(RegExp(r'^-+|-+$'), '');
  if (slug.isEmpty) slug = 'casella';
  final used = taken.toSet();
  var id = 'mb-$slug';
  var n = 2;
  while (used.contains(id)) {
    id = 'mb-$slug-$n';
    n++;
  }
  return id;
}

List<Map<String, dynamic>> priorityLabels(int n, String provider, [String prefix = 'Neura-P']) {
  return [
    for (var rank = 0; rank < n; rank++)
      {
        'rank': rank,
        'provider_label': folderForRank(rank, provider, prefix),
        'text': 'Priorità ${rank + 1}',
      },
  ];
}

/// Cartella del rango interno 0, la più urgente. Con order=asc è l'ultima.
String mostUrgentFolder(int n, String order, String provider, String prefix) {
  final slot = order == 'asc' ? n - 1 : 0;
  return folderForRank(slot, provider, prefix);
}

/// Nome visibile: INBOX.BeC-P4 diventa BeC-P4.
String folderLeaf(String label) {
  final leaf = label.split('.').last.trim();
  return leaf.isEmpty ? label : leaf;
}

String folderForRank(int rank, String provider, String prefix) {
  final stem = prefix.trim().isEmpty ? 'Neura-P' : prefix.trim();
  final numbered = '$stem${rank + 1}';
  if (provider == 'imap' && !stem.toUpperCase().startsWith('INBOX')) {
    return 'INBOX.$numbered';
  }
  return numbered;
}

String _inferPrefix(Object? labels) {
  if (labels is! List || labels.isEmpty || labels.first is! Map) return 'Neura-P';
  final raw = (labels.first as Map)['provider_label']?.toString() ?? '';
  final leaf = raw.split('.').last;
  final digits = RegExp(r'\d+$').firstMatch(leaf);
  if (digits == null || digits.start == 0) return 'Neura-P';
  return leaf.substring(0, digits.start);
}

/// Turns an engine line into a sentence to show immediately.
String? statusFromLine(String line, S s) {
  final text = line.trim().toLowerCase();
  if (text.isEmpty) return null;
  if (text.contains('login rejected')) return s.passwordRejected;
  if (text.contains('set neura_imap_password') || text.contains('password missing')) {
    return s.passwordMissing;
  }
  if (text.contains('login ok')) return s.loginOk;
  if (text.startsWith('labels: yes')) return s.canLabel;
  if (text.startsWith('labels: no')) return s.foldersOnlyProvider;
  if (text.contains('classifying unread')) return s.classifyingUnread;
  if (text.contains('nightly observation')) return s.closingRead;
  if (text.contains('learned ')) return s.learningMoves;
  if (text.contains('connecting')) return s.connectingMailbox;
  if (text.contains('creating priority folders')) return s.creatingFolders;
  if (text.contains('recipients of sent') || text.contains('sent mail') || text.contains('sent messages')) {
    return s.countingSent;
  }
  if (text.startsWith('error')) return s.failed;
  return null;
}

bool lineIsFailure(String line) {
  final text = line.toLowerCase();
  return text.contains('login rejected') || text.startsWith('error') || text.contains('neura_imap_password');
}

class RecentDecision {
  const RecentDecision({
    required this.fromAddr,
    required this.rank,
    required this.stage,
    required this.confidence,
    required this.label,
  });

  final String fromAddr;
  final int rank;
  final String stage;
  final double confidence;
  final String label;
}

class NeuraStats {
  NeuraStats({
    required this.open,
    required this.corrections,
    required this.confirmations,
    required this.replies,
    required this.labeled,
    required this.expired,
    required this.correctionsPer100,
    required this.accuracy,
    required this.mae,
    required this.stages,
    required this.ranks,
    required this.recent,
  });

  final int open;
  final int corrections;
  final int confirmations;
  final int replies;
  final int labeled;
  final int expired;
  final double correctionsPer100;
  final double accuracy;
  final double mae;
  final Map<String, int> stages;
  final Map<int, int> ranks;
  final List<RecentDecision> recent;

  static NeuraStats? parse(String output) {
    int? field(String name) {
      final match = RegExp('$name: (\\d+)').firstMatch(output);
      return match == null ? null : int.parse(match.group(1)!);
    }

    double? decimal(String name) {
      final match = RegExp('$name: ([0-9.]+)').firstMatch(output);
      return match == null ? null : double.parse(match.group(1)!);
    }

    final open = field('open');
    final corrections = field('corrections');
    final confirmations = field('confirmations');
    if (open == null || corrections == null || confirmations == null) {
      return null;
    }
    final stages = <String, int>{};
    for (final match in RegExp(r'stage (\w+): (\d+)').allMatches(output)) {
      stages[match.group(1)!] = int.parse(match.group(2)!);
    }
    final ranks = <int, int>{};
    for (final match in RegExp(r'rank (\d+): (\d+)').allMatches(output)) {
      ranks[int.parse(match.group(1)!)] = int.parse(match.group(2)!);
    }
    final recent = <RecentDecision>[];
    for (final line in output.split('\n')) {
      if (!line.startsWith('recent\t')) continue;
      final parts = line.split('\t');
      if (parts.length < 6) continue;
      recent.add(
        RecentDecision(
          fromAddr: parts[1],
          rank: int.tryParse(parts[2]) ?? 0,
          stage: parts[3],
          confidence: double.tryParse(parts[4]) ?? 0,
          label: parts.sublist(5).join('\t'),
        ),
      );
    }
    return NeuraStats(
      open: open,
      corrections: corrections,
      confirmations: confirmations,
      replies: field('replies') ?? 0,
      labeled: field('labeled') ?? 0,
      expired: field('expired') ?? 0,
      correctionsPer100: decimal('corrections/100') ?? 0,
      accuracy: decimal('accuracy') ?? 0,
      mae: decimal('mae') ?? 0,
      stages: stages,
      ranks: ranks,
      recent: recent,
    );
  }
}
