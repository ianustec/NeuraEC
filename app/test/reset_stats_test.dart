import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:neura_app/engine.dart';
import 'package:neura_app/mailbox_config.dart';

void main() {
  test('azzerare toglie il registro e lascia l\'apprendimento', () async {
    final home = await Directory.systemTemp.createTemp('neura-reset');
    final engine = NeuraEngine(home: home);
    const id = 'mb-demo';
    final box = Directory('${home.path}/data/mailboxes/$id')..createSync(recursive: true);
    File('${box.path}/pred.sqlite').writeAsStringSync('registro');
    File('${box.path}/pred.sqlite-wal').writeAsStringSync('wal');
    final learned = File('${home.path}/data/users/me/state.json');
    learned.parent.createSync(recursive: true);
    learned.writeAsStringSync('{"initialized_at":"x"}');
    final slot = MailboxSlot(
      config: MailboxConfig(
        mailboxId: id,
        userId: 'me',
        ownAddresses: const ['io@dominio.it'],
        n: 4,
        order: 'asc',
        provider: 'imap',
        host: 'imap.dominio.it',
        username: 'io@dominio.it',
        port: 993,
        tls: 'ssl',
      ),
      password: '',
      primary: true,
    );
    await engine.resetStats(slot);
    expect(File('${box.path}/pred.sqlite').existsSync(), isFalse);
    expect(File('${box.path}/pred.sqlite-wal').existsSync(), isFalse);
    expect(learned.existsSync(), isTrue);
    await home.delete(recursive: true);
  });

  test('l\'intervallo è globale e resta 1, 5 o 15', () async {
    final home = await Directory.systemTemp.createTemp('neura-interval');
    final engine = NeuraEngine(home: home);
    expect(await engine.loadIntervalMinutes(), 5);
    await engine.saveNotificationsOn(true);
    await engine.saveIntervalMinutes(1);
    expect(await engine.loadIntervalMinutes(), 1);
    expect(await engine.loadNotificationsOn(), isTrue);
    await engine.saveIntervalMinutes(15);
    expect(await engine.loadIntervalMinutes(), 15);
    await engine.saveIntervalMinutes(9);
    expect(await engine.loadIntervalMinutes(), 5);
    await home.delete(recursive: true);
  });
}
