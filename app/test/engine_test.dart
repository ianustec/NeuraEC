import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:neura_app/engine.dart';
import 'package:neura_app/mailbox_config.dart';

void main() {
  test('una seconda casella si salva accanto, senza la password nel json', () async {
    final home = await Directory.systemTemp.createTemp('neura-caselle');
    final engine = NeuraEngine(home: home);
    await engine.saveSlot(
      MailboxSlot(
        config: MailboxConfig(
          mailboxId: 'mb-locale',
          userId: 'me',
          ownAddresses: const ['a@b.it'],
          n: 4,
          order: 'asc',
          provider: 'imap',
          host: 'imap.example',
          username: 'a@b.it',
          port: 993,
          tls: 'ssl',
          labelPrefix: 'BeC-P',
        ),
        password: 'secret-a',
        primary: true,
      ),
    );
    final id = mailboxIdFor('c@d.it', const ['mb-locale']);
    await engine.saveSlot(
      MailboxSlot(
        config: MailboxConfig(
          mailboxId: id,
          userId: id.substring(3),
          ownAddresses: const ['c@d.it'],
          n: 4,
          order: 'asc',
          provider: 'imap',
          host: 'imap.altro',
          username: 'c@d.it',
          port: 993,
          tls: 'ssl',
        ),
        password: 'secret-b',
        primary: false,
      ),
    );

    final slots = await engine.loadSlots();
    expect(slots, hasLength(2));
    expect(slots.first.primary, isTrue);
    expect(slots.last.config.username, 'c@d.it');
    final json = await File('${home.path}/mailboxes/$id.json').readAsString();
    expect(json.contains('secret'), isFalse);
    expect(await File('${home.path}/mailboxes/$id.password').readAsString(), 'secret-b');
    expect(await File('${home.path}/password').readAsString(), 'secret-a');

    await engine.deleteSlot(slots.last);
    expect(await engine.loadSlots(), hasLength(1));
    await home.delete(recursive: true);
  });
}
