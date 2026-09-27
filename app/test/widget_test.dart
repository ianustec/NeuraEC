import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:neura_app/dashboard.dart';
import 'package:neura_app/i18n/s.dart';
import 'package:neura_app/main.dart';
import 'package:neura_app/neural_activity.dart';

void main() {
  testWidgets('la prima pagina mostra il modello', (tester) async {
    await tester.binding.setSurfaceSize(const Size(1400, 1000));
    await tester.pumpWidget(const NeuraApp(initialLocale: Locale('it')));
    await tester.pump();
    expect(find.text('NeuraEC'), findsWidgets);
    expect(find.text('Come decide'), findsOneWidget);
    expect(find.text('1 min'), findsOneWidget);
    expect(find.text('5 min'), findsOneWidget);
    expect(find.text('15 min'), findsOneWidget);
    expect(find.text('Per tutte le caselle'), findsOneWidget);
    expect(find.text('RELEASE'), findsOneWidget);
    expect(find.text('1.0.0'), findsOneWidget);
    await tester.tap(find.text('Caselle'));
    await tester.pump();
    expect(find.text('Aggiungi casella'), findsOneWidget);
    expect(find.text('Host IMAP'), findsOneWidget);
    expect(find.text('Azzera statistiche'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('con due caselle la home le mostra come linguette', (tester) async {
    var chosen = 0;
    await tester.pumpWidget(
      AppText(
        s: S('it'),
        child: MaterialApp(
        home: Scaffold(
          body: NeuraDashboard(
            stats: null,
            mailboxes: const ['a@b.it', 'c@d.it'],
            selected: 0,
            onSelect: (index) => chosen = index,
            order: 'asc',
            n: 4,
            prefix: 'BeC-P',
            busy: false,
            loading: false,
            serviceOn: false,
            onRefresh: () {},
            onClassify: () {},
            onToggleService: () {},
            onStop: () {},
          ),
        ),
        ),
      ),
    );
    expect(find.text('a@b.it'), findsOneWidget);
    expect(find.text('c@d.it'), findsOneWidget);
    await tester.tap(find.text('c@d.it'));
    expect(chosen, 1);
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('durante il lavoro compare la rete con la frase in corso', (tester) async {
    await tester.pumpWidget(
      AppText(
        s: S('it'),
        child: const MaterialApp(
          home: Scaffold(body: NeuralActivity(caption: 'Cerco le mail non lette…', busy: true)),
        ),
      ),
    );
    expect(tester.takeException(), isNull);
    expect(find.text('IN ELABORAZIONE'), findsOneWidget);
    expect(find.text('Cerco le mail non lette…'), findsOneWidget);
    await tester.pump(const Duration(milliseconds: 700));
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('la rete sta dentro la card anche stretta', (tester) async {
    await tester.pumpWidget(
      AppText(
        s: S('it'),
        child: const MaterialApp(
          home: Scaffold(
            body: SizedBox(width: 420, height: 112, child: NeuralActivity()),
          ),
        ),
      ),
    );
    await tester.pump();
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('la lingua si cambia e la home segue', (tester) async {
    await tester.binding.setSurfaceSize(const Size(1400, 1000));
    await tester.pumpWidget(const NeuraApp(initialLocale: Locale('en')));
    await tester.pump();
    expect(find.text('How it decides'), findsOneWidget);
    expect(find.text('Mailboxes'), findsOneWidget);
    await tester.tap(find.text('EN'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    await tester.tap(find.text('Français').last);
    await tester.pump();
    expect(find.text('Comment il décide'), findsOneWidget);
    expect(find.text('Boîtes'), findsWidgets);
    await tester.pumpWidget(const SizedBox());
  });
}
