import 'package:flutter/material.dart';

/// Colori del portale NEURA (iastack-dashboard).
class NeuraColors {
  static const bg = Color(0xFF0A0A0F);
  static const text = Color(0xFFE8E8ED);
  static const muted = Color(0x99E8E8ED);
  static const cyan = Color(0xFF00D4FF);
  static const magenta = Color(0xFFFF00E5);
  static const border = Color(0x3300D4FF);
  static const card = Color(0x8C0A0A0F);
}

class NeuraBackdrop extends StatelessWidget {
  const NeuraBackdrop({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        const ColoredBox(color: NeuraColors.bg),
        const Positioned.fill(child: CustomPaint(painter: _GridPainter())),
        child,
      ],
    );
  }
}

class _GridPainter extends CustomPainter {
  const _GridPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = const Color(0x0800D4FF)
      ..strokeWidth = 1;
    const step = 48.0;
    for (var x = 0.0; x <= size.width; x += step) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), paint);
    }
    for (var y = 0.0; y <= size.height; y += step) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class NeuraSectionTitle extends StatelessWidget {
  const NeuraSectionTitle(this.label, {super.key, this.magenta = false});

  final String label;
  final bool magenta;

  @override
  Widget build(BuildContext context) {
    final color = magenta ? NeuraColors.magenta : NeuraColors.cyan;
    return Row(
      children: [
        Text(
          label.toUpperCase(),
          style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w800, letterSpacing: 1.8),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Container(
            height: 1,
            decoration: BoxDecoration(
              gradient: LinearGradient(colors: [color.withValues(alpha: 0.45), color.withValues(alpha: 0)]),
            ),
          ),
        ),
      ],
    );
  }
}

BoxDecoration neuraCardDecoration({bool magenta = false}) {
  final border = magenta ? const Color(0x2EFF00E5) : NeuraColors.border;
  return BoxDecoration(
    color: const Color(0x8C0A0A0F),
    borderRadius: BorderRadius.circular(16),
    border: Border.all(color: border),
  );
}
