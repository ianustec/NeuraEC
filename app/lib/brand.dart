import 'package:flutter/material.dart';

class IanustecLogo extends StatelessWidget {
  const IanustecLogo({super.key, this.height = 22});

  final double height;

  @override
  Widget build(BuildContext context) {
    return Image.asset(
      'assets/ianustec_black_no_payoff.png',
      height: height,
      fit: BoxFit.contain,
      alignment: Alignment.centerLeft,
    );
  }
}

class NeuraSphere extends StatelessWidget {
  const NeuraSphere({super.key, this.size = 46});

  final double size;

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(size * 0.28),
      child: Image.asset(
        'assets/neuraec_icon_v2.png',
        width: size,
        height: size,
        fit: BoxFit.cover,
      ),
    );
  }
}
