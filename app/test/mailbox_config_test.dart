import 'package:flutter_test/flutter_test.dart';
import 'package:neura_app/i18n/s.dart';
import 'package:neura_app/mailbox_config.dart';

void main() {
  test('un utente nuovo riceve un id libero', () {
    expect(mailboxIdFor('t.benedetti@ianustec.com', const []), 'mb-t-benedetti');
    expect(mailboxIdFor('t.benedetti@ianustec.com', const ['mb-t-benedetti']), 'mb-t-benedetti-2');
    expect(mailboxIdFor('t.benedetti@ianustec.com', const ['mb-locale']), 'mb-t-benedetti');
  });

  test('il nome di default è Neura-P e si può cambiare', () {
    final imap = priorityLabels(4, 'imap');
    final custom = priorityLabels(2, 'imap', 'Urgente');
    expect(imap.first['provider_label'], 'INBOX.Neura-P1');
    expect(imap.last['provider_label'], 'INBOX.Neura-P4');
    expect(custom.first['provider_label'], 'INBOX.Urgente1');
    expect(priorityLabels(3, 'gmail', 'N-P').first['provider_label'], 'N-P1');
  });

  test('la password non entra nel json della casella', () {
    final config = MailboxConfig(
      mailboxId: 'mb',
      userId: 'me',
      ownAddresses: const ['io@dominio.it'],
      n: 4,
      order: 'desc',
      provider: 'imap',
      host: 'imap.dominio.it',
      username: 'io@dominio.it',
      port: 993,
      tls: 'ssl',
      labelPrefix: 'N-P',
    );
    expect(config.encode().contains('password'), isFalse);
    final again = MailboxConfig.fromJson(config.toJson());
    expect(again.host, 'imap.dominio.it');
    expect(again.n, 4);
    expect(again.ownAddresses, ['io@dominio.it']);
  });

  test('una riga di login diventa uno stato leggibile', () {
    final it = S('it');
    expect(statusFromLine('connecting to the mailbox…', it), 'Connessione alla casella…');
    expect(statusFromLine('login ok', it), 'Accesso riuscito');
    expect(statusFromLine('login rejected: AUTH', it), 'Password rifiutata');
    expect(loginFeedback('login ok', it), 'Accesso riuscito');
    expect(loginFeedback('login rejected: AUTHENTICATIONFAILED', it), 'Password rifiutata');
    expect(loginFeedback('login rejected: [Errno 8] nodename nor servname', it), 'Accesso non riuscito: [Errno 8] nodename nor servname');
    expect(statusFromLine('reading recipients of sent mail from the last 90 days', it), contains('90 giorni'));
    expect(statusFromLine('mailbox mb: classifying unread', it), 'Classifico le mail non lette…');
    expect(statusFromLine('login ok', S('en')), 'Signed in');
    expect(statusFromLine('login rejected: AUTH', S('fr')), 'Mot de passe refusé');
    expect(statusFromLine('login ok', S('de')), 'Angemeldet');
    expect(statusFromLine('password missing', S('es')), 'Falta la contraseña');
    expect(lineIsFailure('login rejected: no'), isTrue);
    expect(lineIsFailure('login ok'), isFalse);
  });

  test('le statistiche si leggono dall\'output della CLI', () {
    const output = '''
open: 2
corrections: 1
confirmations: 3
replies: 0
labeled: 4
corrections/100: 25.0
accuracy: 0.75
mae: 0.25
''';
    final stats = NeuraStats.parse(output);
    expect(stats, isNotNull);
    expect(stats!.open, 2);
    expect(stats.corrections, 1);
    expect(stats.correctionsPer100, 25);
    expect(stats.accuracy, 0.75);
  });

  test('il modello si legge dagli stage e dalle ultime decisioni', () {
    const output = '''
open: 2
corrections: 0
confirmations: 0
replies: 0
labeled: 0
corrections/100: 0.0
accuracy: 0.0
mae: 0.0
expired: 1
stage sender: 2
stage prior: 0
rank 3: 2
recent\ta@b.it\t3\tsender\t0.42\tINBOX.BeC-P1
''';
    final stats = NeuraStats.parse(output);
    expect(stats!.stages['sender'], 2);
    expect(stats.ranks[3], 2);
    expect(stats.expired, 1);
    expect(stats.recent.single.fromAddr, 'a@b.it');
    expect(stats.recent.single.label, 'INBOX.BeC-P1');
  });
}
