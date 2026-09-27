import 'package:flutter_test/flutter_test.dart';
import 'package:neura_app/i18n/s.dart';

void main() {
  test('le cinque lingue hanno le stesse frasi', () {
    final keys = S.catalog('it').keys.toSet();
    for (final code in S.codes) {
      expect(S.catalog(code).keys.toSet(), keys, reason: code);
      for (final value in S.catalog(code).values) {
        expect(value.trim(), isNotEmpty, reason: code);
      }
    }
  });
}
