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
    required String account,
    required String waiting,
    required String per100,
    required String accuracy,
    required bool serviceOn,
    Map<String, String> labels = const {},
  }) async {
    try {
      await _channel.invokeMethod('update', {
        'account': account,
        'waiting': waiting,
        'per100': per100,
        'accuracy': accuracy,
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
}
