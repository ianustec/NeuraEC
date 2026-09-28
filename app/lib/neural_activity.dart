import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'i18n/s.dart';

/// Rete animata. Non calcola nulla: è il segnale visivo della home.
class NeuralActivity extends StatefulWidget {
  const NeuralActivity({
    super.key,
    this.caption = '',
    this.busy = false,
    this.height,
    this.minutes = 5,
  });

  final String caption;
  final bool busy;
  final double? height;
  final int minutes;

  @override
  State<NeuralActivity> createState() => _NeuralActivityState();
}

class _NeuralActivityState extends State<NeuralActivity>
    with SingleTickerProviderStateMixin {
  late final AnimationController _flow;

  @override
  void initState() {
    super.initState();
    _flow = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 2800))
      ..repeat();
  }

  @override
  void dispose() {
    _flow.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = AppText.of(context);
    final working = widget.busy && widget.caption.isNotEmpty;
    return LayoutBuilder(
      builder: (context, constraints) {
        final maxW = constraints.maxWidth.isFinite ? constraints.maxWidth : 640.0;
        const textFloor = 300.0;
        final netW = math.min(280.0, math.max(96.0, maxW - textFloor));
        final cardW = math.min(maxW, textFloor + netW + 42);
        return Align(
          alignment: Alignment.centerRight,
          child: SizedBox(
            width: cardW,
            height: widget.height,
            child: DecoratedBox(
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(24),
                boxShadow: const [
                  BoxShadow(
                      color: Color(0x120B3040),
                      blurRadius: 24,
                      offset: Offset(0, 10))
                ],
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(24),
                child: Row(
                  children: [
                    Expanded(
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(22, 12, 12, 12),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Text(
                              working ? s.processing : s.listeningBadge,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                color: Color(0xFF00A8CC),
                                fontSize: 11,
                                fontWeight: FontWeight.w800,
                                letterSpacing: 1.4,
                              ),
                            ),
                            const SizedBox(height: 6),
                            Text(
                              working ? widget.caption : s.every(widget.minutes),
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                color: Color(0xFF12141A),
                                fontSize: 20,
                                fontWeight: FontWeight.w800,
                                height: 1.2,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    SizedBox(
                      width: netW,
                      child: RepaintBoundary(
                        child: AnimatedBuilder(
                          animation: _flow,
                          builder: (context, _) {
                            return CustomPaint(
                              painter: _NetPainter(_flow.value),
                              child: const SizedBox.expand(),
                            );
                          },
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}

class _NetPainter extends CustomPainter {
  _NetPainter(this.t);

  final double t;

  static const _counts = [4, 5, 6, 6, 6, 5, 4];
  static const _cyan = Color(0xFF00D4FF);
  static const _violet = Color(0xFF7A5CFF);
  static const _span = 6.0;

  @override
  void paint(Canvas canvas, Size size) {
    final nodes = _layout(size);
    _edges(canvas, nodes);
    _nodes(canvas, nodes);
  }

  List<List<Offset>> _layout(Size size) {
    const preferredGap = 46.0;
    const edge = 18.0;
    final span = _counts.length - 1;
    final step = math.min(preferredGap, (size.width - edge * 2) / span);
    final used = step * span;
    final origin = size.width - edge - used;
    final layers = <List<Offset>>[];
    for (var i = 0; i < _counts.length; i++) {
      final x = origin + step * i;
      final count = _counts[i];
      final layer = <Offset>[];
      for (var j = 0; j < count; j++) {
        final base = 0.1 + 0.8 * (j + 0.5) / count;
        final drift = math.sin(t * math.pi * 2 + i * 1.3 + j * 0.9) * 0.008;
        layer.add(Offset(x, size.height * (base + drift)));
      }
      layers.add(layer);
    }
    return layers;
  }

  void _edges(Canvas canvas, List<List<Offset>> nodes) {
    for (var layer = 0; layer < nodes.length - 1; layer++) {
      final from = nodes[layer];
      final to = nodes[layer + 1];
      final hot = Color.lerp(_cyan, _violet, layer / (_counts.length - 2))!;
      for (var j = 0; j < from.length; j++) {
        for (var k = 0; k < to.length; k++) {
          if (!_linked(j, from.length, k, to.length)) continue;
          final a = from[j];
          final b = to[k];
          final energy = _energy(layer, 0.5);
          final paint = Paint()
            ..color = Color.lerp(const Color(0xFFC5D0E0), hot, energy)!
                .withValues(alpha: 0.42 + 0.5 * energy)
            ..strokeWidth = 1.05 + 1.35 * energy
            ..strokeCap = StrokeCap.round;
          canvas.drawLine(a, b, paint);
          for (final wave in _waves) {
            final along = wave - layer;
            if (along < 0 || along > 1) continue;
            final point = Offset.lerp(a, b, along)!;
            canvas.drawCircle(
              point,
              7,
              Paint()
                ..color = hot.withValues(alpha: 0.28)
                ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 6),
            );
            canvas.drawCircle(point, 3.3, Paint()..color = Colors.white);
            canvas.drawCircle(point, 2.1, Paint()..color = hot);
          }
        }
      }
    }
  }

  void _nodes(Canvas canvas, List<List<Offset>> nodes) {
    for (var layer = 0; layer < nodes.length; layer++) {
      final hot = Color.lerp(_cyan, _violet, layer / (nodes.length - 1))!;
      final incoming = layer == 0 ? 0.0 : _energy(layer - 1, 1);
      final outgoing = layer == nodes.length - 1 ? 0.0 : _energy(layer, 0);
      final energy = math.max(incoming, outgoing);
      for (final point in nodes[layer]) {
        final radius = 4.2 + 1.8 * energy;
        if (energy > 0.08) {
          canvas.drawCircle(
            point,
            radius + 6,
            Paint()
              ..color = hot.withValues(alpha: 0.22 * energy)
              ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 8),
          );
        }
        canvas.drawCircle(point, radius, Paint()..color = Colors.white);
        canvas.drawCircle(
          point,
          radius,
          Paint()
            ..style = PaintingStyle.stroke
            ..strokeWidth = 1.7
            ..color = Color.lerp(const Color(0xFFD0D7E4), hot, energy)!,
        );
        if (energy > 0.35) {
          canvas.drawCircle(point, 2.1, Paint()..color = hot);
        }
      }
    }
  }

  List<double> get _waves => [t * _span, (t * _span + _span / 2) % _span];

  double _energy(int layer, double along) {
    var energy = 0.0;
    for (final wave in _waves) {
      final dist = (wave - layer - along).abs();
      energy = math.max(energy, (1 - dist / 0.55).clamp(0.0, 1.0));
    }
    return energy;
  }

  bool _linked(int j, int n, int k, int m) {
    final a = (j + 0.5) / n;
    final b = (k + 0.5) / m;
    return (a - b).abs() < 0.34;
  }

  @override
  bool shouldRepaint(covariant _NetPainter oldDelegate) => oldDelegate.t != t;
}
