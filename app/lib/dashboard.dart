import 'package:flutter/material.dart';

import 'brand.dart';
import 'i18n/s.dart';
import 'mailbox_config.dart';
import 'neural_activity.dart';

class NeuraDashboard extends StatefulWidget {
  const NeuraDashboard({
    super.key,
    required this.stats,
    required this.mailboxes,
    required this.selected,
    required this.onSelect,
    required this.order,
    required this.n,
    required this.prefix,
    this.provider = 'imap',
    required this.busy,
    this.activity = '',
    required this.loading,
    required this.serviceOn,
    this.live = false,
    required this.onRefresh,
    required this.onClassify,
    required this.onToggleService,
    required this.onStop,
    this.intervalMinutes = 5,
    this.onInterval = _ignoreInterval,
  });

  static void _ignoreInterval(int minutes) {}

  final NeuraStats? stats;
  final List<String> mailboxes;
  final int selected;
  final ValueChanged<int> onSelect;
  final String order;
  final int n;
  final String prefix;
  final String provider;
  final bool busy;
  final String activity;
  final bool loading;
  final bool serviceOn;
  final bool live;
  final VoidCallback onRefresh;
  final VoidCallback onClassify;
  final VoidCallback onToggleService;
  final VoidCallback onStop;
  final int intervalMinutes;
  final ValueChanged<int> onInterval;

  @override
  State<NeuraDashboard> createState() => _NeuraDashboardState();
}

class _NeuraDashboardState extends State<NeuraDashboard> with SingleTickerProviderStateMixin {
  late final AnimationController _pulse;

  @override
  void initState() {
    super.initState();
    _pulse = AnimationController(vsync: this, duration: const Duration(milliseconds: 2800))..repeat();
  }

  @override
  void dispose() {
    _pulse.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final stats = widget.stats;
    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth >= 980;
        return Padding(
          padding: const EdgeInsets.fromLTRB(8, 8, 8, 0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _header(context),
              const SizedBox(height: 22),
              Expanded(
                child: widget.loading
                    ? _skeleton(wide)
                    : ListView(
                  padding: const EdgeInsets.only(bottom: 28),
                  children: [
                    if (wide)
                      IntrinsicHeight(
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Expanded(flex: 3, child: _modelCard(context, stats)),
                            const SizedBox(width: 16),
                            Expanded(flex: 2, child: _heroNumber(context, stats)),
                          ],
                        ),
                      )
                    else ...[
                      _modelCard(context, stats),
                      const SizedBox(height: 16),
                      _heroNumber(context, stats),
                    ],
                    const SizedBox(height: 16),
                    _metricRow(context, stats, wide),
                    const SizedBox(height: 16),
                    if (wide)
                      IntrinsicHeight(
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Expanded(child: _rankCard(context, stats)),
                            const SizedBox(width: 16),
                            Expanded(child: _recentCard(context, stats)),
                          ],
                        ),
                      )
                    else ...[
                      _rankCard(context, stats),
                      const SizedBox(height: 16),
                      _recentCard(context, stats),
                    ],
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _skeleton(bool wide) {
    return AnimatedBuilder(
      animation: _pulse,
      builder: (context, _) {
        final shade = Color.lerp(const Color(0xFFE6EBF3), const Color(0xFFF4F7FB), _pulse.value)!;
        Widget block(double width, double height, {double radius = 8}) {
          return Container(
            width: width,
            height: height,
            decoration: BoxDecoration(color: shade, borderRadius: BorderRadius.circular(radius)),
          );
        }

        Widget line(double factor, {double height = 12}) {
          return Align(
            alignment: Alignment.centerLeft,
            child: FractionallySizedBox(
              widthFactor: factor,
              child: Container(
                height: height,
                decoration: BoxDecoration(color: shade, borderRadius: BorderRadius.circular(6)),
              ),
            ),
          );
        }

        Widget stage() {
          return Column(
            children: [
              Container(width: 36, height: 36, decoration: BoxDecoration(color: shade, shape: BoxShape.circle)),
              const SizedBox(height: 10),
              block(54, 12),
              const SizedBox(height: 8),
              block(28, 18, radius: 6),
              const SizedBox(height: 8),
              block(72, 10),
            ],
          );
        }

        final model = _card(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              line(0.38, height: 20),
              const SizedBox(height: 10),
              line(0.72),
              const SizedBox(height: 22),
              Row(
                children: [
                  for (var i = 0; i < 5; i++) ...[
                    if (i > 0)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 48),
                        child: block(14, 3, radius: 2),
                      ),
                    Expanded(child: stage()),
                  ],
                ],
              ),
              const SizedBox(height: 18),
              line(0.84),
            ],
          ),
        );

        final hero = _card(
          gradient: const LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFFF3FBFF), Color(0xFFF7F2FF)],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              line(0.46),
              const SizedBox(height: 16),
              line(0.55, height: 42),
              const SizedBox(height: 12),
              line(0.7),
              const SizedBox(height: 8),
              line(0.9),
              const SizedBox(height: 16),
              line(1, height: 8),
            ],
          ),
        );

        Widget metric() {
          return _card(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                line(0.5),
                const SizedBox(height: 12),
                line(0.42, height: 28),
                const SizedBox(height: 10),
                line(0.78, height: 10),
              ],
            ),
          );
        }

        final ranks = _card(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              line(0.46, height: 18),
              const SizedBox(height: 8),
              line(0.34, height: 10),
              const SizedBox(height: 20),
              SizedBox(
                height: 120,
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    for (final height in [36.0, 96.0, 58.0, 78.0])
                      Expanded(
                        child: Align(alignment: Alignment.bottomCenter, child: block(36, height, radius: 10)),
                      ),
                  ],
                ),
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  for (var i = 0; i < 4; i++) Expanded(child: Center(child: block(48, 10))),
                ],
              ),
            ],
          ),
        );

        Widget decision() {
          return Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Row(
              children: [
                Container(width: 28, height: 28, decoration: BoxDecoration(color: shade, shape: BoxShape.circle)),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      line(0.62),
                      const SizedBox(height: 6),
                      line(0.4, height: 10),
                    ],
                  ),
                ),
                const SizedBox(width: 12),
                block(52, 14),
              ],
            ),
          );
        }

        final recent = _card(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              line(0.5, height: 18),
              const SizedBox(height: 8),
              line(0.38, height: 10),
              const SizedBox(height: 8),
              for (var i = 0; i < 4; i++) decision(),
            ],
          ),
        );

        return ListView(
          padding: const EdgeInsets.only(bottom: 28),
          children: [
            if (wide)
              IntrinsicHeight(
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Expanded(flex: 3, child: model),
                    const SizedBox(width: 16),
                    Expanded(flex: 2, child: hero),
                  ],
                ),
              )
            else ...[
              model,
              const SizedBox(height: 16),
              hero,
            ],
            const SizedBox(height: 16),
            if (wide)
              Row(
                children: [
                  for (var i = 0; i < 4; i++) ...[
                    if (i > 0) const SizedBox(width: 16),
                    Expanded(child: metric()),
                  ],
                ],
              )
            else
              Column(
                children: [
                  for (var i = 0; i < 4; i++) ...[
                    if (i > 0) const SizedBox(height: 16),
                    metric(),
                  ],
                ],
              ),
            const SizedBox(height: 16),
            if (wide)
              IntrinsicHeight(
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Expanded(child: ranks),
                    const SizedBox(width: 16),
                    Expanded(child: recent),
                  ],
                ),
              )
            else ...[
              ranks,
              const SizedBox(height: 16),
              recent,
            ],
          ],
        );
      },
    );
  }

  Widget _header(BuildContext context) {
    final s = AppText.of(context);
    final chips = widget.mailboxes.length <= 1
        ? const SizedBox.shrink()
        : Padding(
            padding: const EdgeInsets.only(top: 10),
            child: widget.mailboxes.length > 2 ? _mailboxMenu() : _tabs(),
          );
    final showNet = widget.serviceOn || widget.live;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'NeuraEC',
                    style: TextStyle(fontSize: 36, fontWeight: FontWeight.w800, color: Color(0xFF12141A), height: 1),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    widget.serviceOn ? s.listeningFor(widget.intervalMinutes) : s.idleFor(widget.intervalMinutes),
                    style: const TextStyle(color: Color(0xFF5C6478), fontSize: 15),
                  ),
                ],
              ),
            ),
            const Padding(
              padding: EdgeInsets.only(top: 6, left: 16),
              child: IanustecLogo(height: 22),
            ),
          ],
        ),
        const SizedBox(height: 14),
        _interval(s),
        const SizedBox(height: 16),
        SizedBox(
          height: _netBand,
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _buttons(),
                  chips,
                ],
              ),
              const SizedBox(width: 28),
              Expanded(
                child: AnimatedSwitcher(
                  duration: const Duration(milliseconds: 280),
                  child: showNet
                      ? NeuralActivity(
                          key: const ValueKey('net'),
                          caption: widget.activity,
                          busy: widget.live,
                          minutes: widget.intervalMinutes,
                        )
                      : const SizedBox.shrink(key: ValueKey('none')),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  static const double _netBand = 112;

  Widget _interval(S s) {
    return Row(
      children: [
        for (final minutes in const [1, 5, 15]) ...[
          _intervalChip(s.minutesLabel(minutes), minutes == widget.intervalMinutes, () => widget.onInterval(minutes)),
          const SizedBox(width: 8),
        ],
        Text(s.intervalScope, style: const TextStyle(color: Color(0xFF5C6478), fontSize: 13)),
      ],
    );
  }

  Widget _intervalChip(String label, bool selected, VoidCallback onTap) {
    return Material(
      color: selected ? const Color(0xFF12141A) : Colors.white,
      borderRadius: BorderRadius.circular(999),
      child: InkWell(
        borderRadius: BorderRadius.circular(999),
        onTap: widget.busy ? null : onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          child: Text(
            label,
            style: TextStyle(
              fontWeight: FontWeight.w700,
              color: selected ? Colors.white : const Color(0xFF12141A),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buttons() {
    final s = AppText.of(context);
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        if (widget.busy)
          FilledButton.icon(
            onPressed: widget.onStop,
            icon: const Icon(Icons.stop, size: 18),
            label: Text(s.stop),
            style: _pill(filled: true),
          )
        else
          FilledButton.icon(
            onPressed: widget.onToggleService,
            icon: Icon(widget.serviceOn ? Icons.stop : Icons.play_arrow, size: 18),
            label: Text(widget.serviceOn ? s.stopClassification : s.startClassification),
            style: _pill(filled: true),
          ),
        const SizedBox(width: 8),
        FilledButton(
          onPressed: widget.busy ? null : widget.onClassify,
          style: _pill(filled: false),
          child: Text(s.onePass),
        ),
        const SizedBox(width: 8),
        _roundButton(Icons.refresh, s.refresh, widget.busy ? null : widget.onRefresh),
      ],
    );
  }

  static const double _control = 44;

  ButtonStyle _pill({required bool filled}) {
    return FilledButton.styleFrom(
      backgroundColor: filled ? const Color(0xFF12141A) : const Color(0xFFD7F1F8),
      foregroundColor: filled ? Colors.white : const Color(0xFF12141A),
      minimumSize: const Size(0, _control),
      fixedSize: const Size.fromHeight(_control),
      padding: const EdgeInsets.symmetric(horizontal: 16),
      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
      visualDensity: VisualDensity.standard,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(_control / 2)),
    );
  }

  Widget _roundButton(IconData icon, String tooltip, VoidCallback? onPressed) {
    return IconButton(
      tooltip: tooltip,
      onPressed: onPressed,
      icon: Icon(icon, size: 20),
      style: IconButton.styleFrom(
        backgroundColor: const Color(0xFFD7F1F8),
        foregroundColor: const Color(0xFF12141A),
        fixedSize: const Size(_control, _control),
        minimumSize: const Size(_control, _control),
        maximumSize: const Size(_control, _control),
        padding: EdgeInsets.zero,
        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
        shape: const CircleBorder(),
      ),
    );
  }

  Widget _mailboxMenu() {
    final selected = widget.mailboxes[widget.selected.clamp(0, widget.mailboxes.length - 1)];
    return PopupMenuButton<int>(
      enabled: !widget.busy,
      tooltip: AppText.of(context).navMailboxes,
      onSelected: widget.onSelect,
      itemBuilder: (context) => [
        for (var i = 0; i < widget.mailboxes.length; i++)
          PopupMenuItem(
            value: i,
            child: Text(
              widget.mailboxes[i],
              style: TextStyle(fontWeight: i == widget.selected ? FontWeight.w800 : FontWeight.w500),
            ),
          ),
      ],
      child: Container(
        padding: const EdgeInsets.fromLTRB(16, 10, 12, 10),
        decoration: BoxDecoration(
          color: const Color(0xFF12141A),
          borderRadius: BorderRadius.circular(999),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 280),
              child: Text(
                selected,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontWeight: FontWeight.w700, color: Colors.white),
              ),
            ),
            const SizedBox(width: 6),
            const Icon(Icons.expand_more, color: Colors.white, size: 18),
          ],
        ),
      ),
    );
  }

  Widget _tabs() {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        for (var i = 0; i < widget.mailboxes.length; i++)
          _tab(widget.mailboxes[i], i == widget.selected, () => widget.onSelect(i)),
      ],
    );
  }

  Widget _tab(String label, bool selected, VoidCallback onTap) {
    return Material(
      color: selected ? const Color(0xFF12141A) : Colors.white,
      borderRadius: BorderRadius.circular(999),
      child: InkWell(
        borderRadius: BorderRadius.circular(999),
        onTap: widget.busy ? null : onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          child: Text(
            label,
            style: TextStyle(
              fontWeight: FontWeight.w700,
              color: selected ? Colors.white : const Color(0xFF12141A),
            ),
          ),
        ),
      ),
    );
  }

  Widget _modelCard(BuildContext context, NeuraStats? stats) {
    final s = AppText.of(context);
    final stages = [
      ('thread', s.stageThread, s.stageThreadHint, Icons.forum_outlined),
      ('sender', s.stageSender, s.stageSenderHint, Icons.person_outline),
      ('domain', s.stageDomain, s.stageDomainHint, Icons.language),
      ('memory', s.stageMemory, s.stageMemoryHint, Icons.hub_outlined),
      ('prior', s.stagePrior, s.stagePriorHint, Icons.auto_awesome_outlined),
    ];
    return _card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(s.howItDecides, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: Color(0xFF12141A))),
          const SizedBox(height: 4),
          Text(
            s.fiveLooks,
            style: const TextStyle(color: Color(0xFF5C6478), height: 1.35),
          ),
          const SizedBox(height: 18),
          AnimatedBuilder(
            animation: _pulse,
            builder: (context, _) {
              return Row(
                children: [
                  for (var i = 0; i < stages.length; i++) ...[
                    if (i > 0) _link(i),
                    Expanded(child: _stage(stages[i], stats?.stages[stages[i].$1] ?? 0, i)),
                  ],
                ],
              );
            },
          ),
          const SizedBox(height: 16),
          Text(
            s.youMove,
            style: const TextStyle(color: Color(0xFF5C6478), fontSize: 13, height: 1.4),
          ),
        ],
      ),
    );
  }

  Widget _link(int index) {
    final lit = ((_pulse.value * 5) - (index - 1)).clamp(0.0, 1.0);
    return Container(
      width: 14,
      height: 3,
      margin: const EdgeInsets.only(bottom: 36),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(2),
        gradient: LinearGradient(
          colors: [
            Color.lerp(const Color(0xFFD5E4EE), const Color(0xFF0099CC), lit)!,
            const Color(0xFFD5E4EE),
          ],
        ),
      ),
    );
  }

  Widget _stage((String, String, String, IconData) stage, int count, int index) {
    final hot = ((_pulse.value * 5) - index).abs() < 0.35;
    return Column(
      children: [
        AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          width: 54,
          height: 54,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: hot
                  ? const [Color(0xFF7AEBFF), Color(0xFFA050FF)]
                  : const [Color(0xFFF4FBFD), Color(0xFFE7F4F8)],
            ),
            boxShadow: [
              if (hot) const BoxShadow(color: Color(0x3319B4C8), blurRadius: 16, offset: Offset(0, 6)),
            ],
          ),
          child: Icon(stage.$4, color: const Color(0xFF12141A)),
        ),
        const SizedBox(height: 8),
        Text(stage.$2, style: const TextStyle(fontWeight: FontWeight.w700, color: Color(0xFF12141A))),
        Text('$count', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: Color(0xFF0099CC))),
        Text(
          stage.$3,
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 11, color: Color(0xFF5C6478), height: 1.25),
        ),
      ],
    );
  }

  Widget _heroNumber(BuildContext context, NeuraStats? stats) {
    final s = AppText.of(context);
    final value = stats?.correctionsPer100 ?? 0;
    return _card(
      gradient: const LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [Color(0xFFE7FBFF), Color(0xFFF4E9FF)],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(s.numberThatCounts, style: const TextStyle(color: Color(0xFF0099CC), fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          Text(
            value.toStringAsFixed(2),
            style: const TextStyle(color: Color(0xFF12141A), fontSize: 64, fontWeight: FontWeight.w800, height: 0.95),
          ),
          Text(s.correctionsEvery100, style: const TextStyle(color: Color(0xFF12141A), fontSize: 18, fontWeight: FontWeight.w600)),
          const SizedBox(height: 12),
          Text(
            s.correctionsExplain,
            style: const TextStyle(color: Color(0xFF5C6478), height: 1.35),
          ),
          const SizedBox(height: 16),
          ClipRRect(
            borderRadius: BorderRadius.circular(99),
            child: LinearProgressIndicator(
              minHeight: 8,
              value: (value / 100).clamp(0, 1),
              backgroundColor: const Color(0x2200D4FF),
              color: const Color(0xFF00D4FF),
            ),
          ),
        ],
      ),
    );
  }

  Widget _metricRow(BuildContext context, NeuraStats? stats, bool wide) {
    final s = AppText.of(context);
    final tiles = [
      _mini(s.classified, '${stats?.open ?? 0}', s.classifiedHint),
      _mini(s.alreadyRight, _alreadyRight(stats), s.alreadyRightHint),
      _mini(s.leftThere, '${stats?.confirmations ?? 0}', s.leftThereHint),
      _mini(s.untouched, '${stats?.expired ?? 0}', s.untouchedHint),
    ];
    if (!wide) {
      return Column(children: [for (final tile in tiles) ...[tile, const SizedBox(height: 10)]]);
    }
    return Row(
      children: [
        for (var i = 0; i < tiles.length; i++) ...[
          if (i > 0) const SizedBox(width: 12),
          Expanded(child: tiles[i]),
        ],
      ],
    );
  }

  String _alreadyRight(NeuraStats? stats) {
    if (stats == null || stats.labeled == 0) return '—';
    return '${(stats.accuracy * 100).round()}%';
  }

  Widget _mini(String label, String value, String caption) {
    return _card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(color: Color(0xFF5C6478), fontWeight: FontWeight.w600)),
          const SizedBox(height: 6),
          Text(value, style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w700, color: Color(0xFF12141A))),
          const SizedBox(height: 4),
          Text(caption, style: const TextStyle(color: Color(0xFF5C6478), fontSize: 12, height: 1.3)),
        ],
      ),
    );
  }

  Widget _rankCard(BuildContext context, NeuraStats? stats) {
    final s = AppText.of(context);
    final counts = [for (var i = 0; i < widget.n; i++) _countForFolder(stats, i)];
    final maxCount = counts.fold<int>(0, (a, b) => a > b ? a : b);
    final urgent = widget.order == 'asc' ? s.lastFolderUrgent : s.firstFolderUrgent;
    return _card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(s.whereTheyGo, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: Color(0xFF12141A))),
          const SizedBox(height: 4),
          Text(urgent, style: const TextStyle(color: Color(0xFF5C6478))),
          const SizedBox(height: 18),
          SizedBox(
            height: 188,
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                for (var i = 0; i < widget.n; i++)
                  Expanded(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 4),
                      child: Column(
                        children: [
                          Text('${counts[i]}', style: const TextStyle(fontWeight: FontWeight.w700, color: Color(0xFF12141A))),
                          const SizedBox(height: 6),
                          Expanded(
                            child: Align(
                              alignment: Alignment.bottomCenter,
                              child: FractionallySizedBox(
                                heightFactor: maxCount == 0 ? 0.08 : (counts[i] / maxCount).clamp(0.08, 1),
                                widthFactor: 0.72,
                                child: DecoratedBox(
                                  decoration: BoxDecoration(
                                    borderRadius: BorderRadius.circular(12),
                                    gradient: LinearGradient(
                                      begin: Alignment.bottomCenter,
                                      end: Alignment.topCenter,
                                      colors: i == (widget.order == 'asc' ? widget.n - 1 : 0)
                                          ? const [Color(0xFF0099CC), Color(0xFF7AEBFF)]
                                          : const [Color(0xFFD7E7EF), Color(0xFFEEF6F8)],
                                    ),
                                  ),
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(height: 8),
                          SizedBox(
                            height: 32,
                            child: Center(
                              child: Text(
                                _folderName(i),
                                textAlign: TextAlign.center,
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, height: 1.15),
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _recentCard(BuildContext context, NeuraStats? stats) {
    final s = AppText.of(context);
    final recent = stats?.recent ?? const <RecentDecision>[];
    return _card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(s.recentTitle, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: Color(0xFF12141A))),
          const SizedBox(height: 4),
          Text(s.recentHint, style: const TextStyle(color: Color(0xFF5C6478))),
          const SizedBox(height: 12),
          if (recent.isEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 24),
              child: Text(s.noneYet, style: const TextStyle(color: Color(0xFF5C6478))),
            )
          else
            for (final item in recent) _recentRow(item),
        ],
      ),
    );
  }

  Widget _recentRow(RecentDecision item) {
    final s = AppText.of(context);
    final folder = item.label.split('.').last;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            alignment: Alignment.center,
            decoration: BoxDecoration(color: const Color(0xFFE7F7FA), borderRadius: BorderRadius.circular(10)),
            child: Text(folder.replaceAll(RegExp(r'\D'), ''), style: const TextStyle(fontWeight: FontWeight.w700, color: Color(0xFF0099CC))),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(item.fromAddr.isEmpty ? s.unknownSender : item.fromAddr, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600)),
                Text(_stageLabel(item.stage), style: const TextStyle(color: Color(0xFF5C6478), fontSize: 12)),
              ],
            ),
          ),
          Text(folder, style: const TextStyle(fontWeight: FontWeight.w700, color: Color(0xFF12141A))),
        ],
      ),
    );
  }

  int _countForFolder(NeuraStats? stats, int folderIndex) {
    final internal = widget.order == 'asc' ? (widget.n - 1) - folderIndex : folderIndex;
    return stats?.ranks[internal] ?? 0;
  }

  String _folderName(int index) {
    final full = folderForRank(index, widget.provider, widget.prefix);
    return full.split('.').last;
  }

  String _stageLabel(String stage) {
    final s = AppText.of(context);
    switch (stage) {
      case 'thread':
        return s.wonThread;
      case 'sender':
        return s.wonSender;
      case 'domain':
        return s.wonDomain;
      case 'memory':
        return s.wonMemory;
      case 'prior':
        return s.wonPrior;
      default:
        return stage;
    }
  }

  Widget _card({required Widget child, Gradient? gradient}) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: gradient == null ? Colors.white : null,
        gradient: gradient,
        borderRadius: BorderRadius.circular(24),
        boxShadow: const [
          BoxShadow(color: Color(0x120B3040), blurRadius: 24, offset: Offset(0, 10)),
        ],
      ),
      child: child,
    );
  }
}
