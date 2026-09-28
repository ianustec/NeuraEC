import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:neura_app/updates.dart';

void main() {
  test('una versione più alta si vede, una uguale o più bassa no', () {
    expect(isNewerVersion('1.0.2', '1.0.1'), isTrue);
    expect(isNewerVersion('v1.0.2', '1.0.1'), isTrue);
    expect(isNewerVersion('1.10.0', '1.9.9'), isTrue);
    expect(isNewerVersion('1.0.1', '1.0.1'), isFalse);
    expect(isNewerVersion('1.0.0', '1.0.1'), isFalse);
    expect(isNewerVersion('nope', '1.0.1'), isFalse);
  });

  test('si sceglie il file del sistema e si ignorano gli altri', () {
    final assets = [
      const ReleaseAsset(name: 'NeuraEC.dmg', url: 'https://example.test/mac'),
      const ReleaseAsset(name: 'NeuraEC-Windows.zip', url: 'https://example.test/win'),
      const ReleaseAsset(name: 'NeuraEC-Linux.tar.gz', url: 'https://example.test/lin'),
      const ReleaseAsset(name: 'NeuraEC-Linux.tar.gz.asc', url: 'https://example.test/asc'),
    ];
    expect(pickAsset(assets, 'macos')?.name, 'NeuraEC.dmg');
    expect(pickAsset(assets, 'windows')?.name, 'NeuraEC-Windows.zip');
    expect(pickAsset(assets, 'linux')?.name, 'NeuraEC-Linux.tar.gz');
    expect(pickAsset(assets, 'ios'), isNull);
  });

  test('la release conta solo se è stabile, più nuova e ha il file giusto', () {
    final mac = _release(assets: const [
      {'name': 'NeuraEC-Windows.zip', 'browser_download_url': 'https://example.test/win', 'size': 10},
    ]);
    expect(interpretRelease(mac, current: '1.0.1', platform: 'macos'), isNull);

    final ready = _release(assets: const [
      {'name': 'NeuraEC.dmg', 'browser_download_url': 'https://example.test/mac', 'size': 12},
      {'name': 'NeuraEC-Linux.tar.gz.asc', 'browser_download_url': 'https://example.test/asc'},
    ]);
    final update = interpretRelease(ready, current: '1.0.1', platform: 'macos');
    expect(update?.version, '1.0.2');
    expect(update?.assetName, 'NeuraEC.dmg');
    expect(update?.url, 'https://example.test/mac');
    expect(update?.size, 12);

    expect(interpretRelease(ready, current: '1.0.2', platform: 'macos'), isNull);
    expect(interpretRelease({...ready, 'prerelease': true}, current: '1.0.1', platform: 'macos'), isNull);
  });

  test('una versione già rimandata non si ripropone e resta nel file', () async {
    expect(shouldPromptUpdate('1.0.2', '1.0.2'), isFalse);
    expect(shouldPromptUpdate('1.0.3', '1.0.2'), isTrue);
    expect(shouldAutoCheck(null, DateTime.utc(2026, 9, 28)), isTrue);
    expect(
      shouldAutoCheck(DateTime.utc(2026, 9, 28, 8), DateTime.utc(2026, 9, 28, 20)),
      isFalse,
    );
    expect(
      shouldAutoCheck(DateTime.utc(2026, 9, 27, 8), DateTime.utc(2026, 9, 28, 9)),
      isTrue,
    );

    final dir = await Directory.systemTemp.createTemp('neura-update');
    addTearDown(() => dir.delete(recursive: true));
    final file = File('${dir.path}/service.json');
    await file.writeAsString('{"notifications": true, "interval_minutes": 5}\n');
    final store = UpdateStore(file);
    await store.rememberSkip('1.0.2');
    await store.rememberCheck(DateTime.utc(2026, 9, 28, 8));
    expect(await store.skippedVersion(), '1.0.2');
    expect(await store.lastChecked(), DateTime.utc(2026, 9, 28, 8));
    final saved = await file.readAsString();
    expect(saved, contains('"notifications": true'));
    expect(saved, contains('"interval_minutes": 5'));
    expect(saved, contains('"update_skipped": "1.0.2"'));
  });
}

Map<String, Object> _release({required List<Map<String, Object>> assets}) {
  return {
    'tag_name': 'v1.0.2',
    'draft': false,
    'prerelease': false,
    'assets': assets,
  };
}
