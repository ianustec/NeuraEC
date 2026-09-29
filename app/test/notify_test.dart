import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:neura_app/notify.dart';

NotifyBatch _batch(List<NotifyItem> items) {
  return NotifyBatch(mailboxId: 'mb-locale', account: 't@ianustec.com', items: items);
}

NotifyItem _item(String label, {int rank = 0, String subject = 'Oggetto', String snippet = 'Anteprima'}) {
  return NotifyItem(rank: rank, label: label, fromAddr: 'a@b.it', subject: subject, snippet: snippet);
}

void main() {
  test('una sola mail porta cartella, account, oggetto e snippet', () {
    final notice = composeNotification(
      _batch([_item('INBOX.BeC-P4', subject: 'Fattura', snippet: 'scadenza')]),
      const ['INBOX.BeC-P4'],
    );
    expect(notice, isNotNull);
    expect(notice!.title, 'BeC-P4 · t@ianustec.com');
    expect(notice.body, 'Fattura\nscadenza');
    expect(notice.account, 't@ianustec.com');
  });

  test('più mail diventano un conteggio per cartella', () {
    final notice = composeNotification(
      _batch([
        _item('INBOX.BeC-P4', rank: 0),
        _item('INBOX.BeC-P4', rank: 0),
        _item('INBOX.BeC-P3', rank: 1),
      ]),
      const ['INBOX.BeC-P4', 'INBOX.BeC-P3'],
    );
    expect(notice!.title, 't@ianustec.com');
    expect(notice.body, '· BeC-P4: 2 email\n· BeC-P3: 1 email');
  });

  test('senza etichette scelte non parte nessun avviso', () {
    final notice = composeNotification(_batch([_item('INBOX.BeC-P4')]), const []);
    expect(notice, isNull);
  });

  test('una mail fuori dalle cartelle scelte non conta', () {
    final notice = composeNotification(
      _batch([_item('INBOX.BeC-P2', rank: 2), _item('INBOX.BeC-P4')]),
      const ['INBOX.BeC-P4'],
    );
    expect(notice!.title, 'BeC-P4 · t@ianustec.com');
  });

  test('la coda si legge, si raggruppa e si svuota', () async {
    final home = await Directory.systemTemp.createTemp('neura-notify');
    final dir = Directory('${home.path}/notify')..createSync();
    File('${dir.path}/b.json').writeAsStringSync('''
{"mailbox_id":"mb-locale","account":"t@ianustec.com","items":[{"rank":0,"label":"INBOX.BeC-P4","from_addr":"a@b.it","subject":"Due","snippet":""}]}
''');
    File('${dir.path}/a.json').writeAsStringSync('''
{"mailbox_id":"mb-locale","account":"t@ianustec.com","items":[{"rank":0,"label":"INBOX.BeC-P4","from_addr":"a@b.it","subject":"Uno","snippet":""}]}
''');
    final batches = await drainNotifyQueue(home);
    expect(batches, hasLength(1));
    expect(batches.single.items.map((item) => item.subject), ['Uno', 'Due']);
    expect(dir.listSync(), isEmpty);
    await home.delete(recursive: true);
  });
}
