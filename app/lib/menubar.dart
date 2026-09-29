import 'dart:io';

import 'package:flutter/services.dart';

/// Icona nella barra dei menu su macOS e nell'area di notifica su Windows.
class MenuBarBridge {
  static const _channel = MethodChannel('it.bentho.neura/menubar');

  static void listen(void Function(bool on) onService) {
    _channel.setMethodCallHandler((call) async {
      if (call.method == 'setService') onService(call.arguments == true);
    });
  }

  static Future<void> update({
    required bool serviceOn,
    Map<String, String> labels = const {},
  }) async {
    try {
      await _channel.invokeMethod('update', {
        'service': serviceOn ? 'on' : 'off',
        ...labels,
      });
    } on MissingPluginException {
      // I test e le piattaforme senza runner macOS non hanno il canale.
    }
  }

  static Future<void> reduce() async {
    try {
      await _channel.invokeMethod('reduce');
    } on MissingPluginException {
      return;
    }
  }

  static Future<void> show() async {
    try {
      await _channel.invokeMethod('show');
    } on MissingPluginException {
      return;
    }
  }

  /// Apre il programma di posta predefinito del sistema, non la finestra di NeuraEC.
  static Future<void> openMail(String account) async {
    try {
      await _channel.invokeMethod('openMail', account);
    } on MissingPluginException {
      if (Platform.isLinux) await _openLinuxMail();
    }
  }

  static Future<void> _openLinuxMail() async {
    final query = await Process.run('xdg-mime', ['query', 'default', 'x-scheme-handler/mailto']);
    final desktop = query.stdout.toString().trim();
    if (desktop.isEmpty) return;
    await Process.run('gtk-launch', [desktop]);
  }
}
