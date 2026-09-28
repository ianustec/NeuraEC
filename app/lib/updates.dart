import 'dart:convert';
import 'dart:io';

/// Public releases of the desktop app.
const updateRepo = 'ianustec/NeuraEC';

const updateAssetNames = {
  'macos': 'NeuraEC.dmg',
  'windows': 'NeuraEC-Windows.zip',
  'linux': 'NeuraEC-Linux.tar.gz',
};

/// A published file the running system can install.
class ReleaseAsset {
  const ReleaseAsset({required this.name, required this.url, this.size});

  final String name;
  final String url;
  final int? size;
}

/// A stable release newer than the one that is running, with a file for this system.
class AvailableUpdate {
  const AvailableUpdate({
    required this.version,
    required this.assetName,
    required this.url,
    this.size,
  });

  final String version;
  final String assetName;
  final String url;
  final int? size;
}

class DownloadCancelled implements Exception {
  const DownloadCancelled();
}

String currentPlatform() {
  if (Platform.isMacOS) return 'macos';
  if (Platform.isWindows) return 'windows';
  if (Platform.isLinux) return 'linux';
  return '';
}

Directory downloadsDirectory() {
  final home = Platform.environment['HOME'] ?? Platform.environment['USERPROFILE'] ?? '';
  if (home.isEmpty) return Directory.systemTemp;
  return Directory('$home${Platform.pathSeparator}Downloads');
}

/// Dotted numbers only. A leading `v` is ignored. Empty or non-numeric text yields nothing.
List<int> versionParts(String raw) {
  var text = raw.trim();
  if (text.startsWith('v') || text.startsWith('V')) text = text.substring(1);
  text = text.split('+').first.split('-').first;
  if (text.isEmpty) return const [];
  final parts = <int>[];
  for (final piece in text.split('.')) {
    final value = int.tryParse(piece);
    if (value == null || value < 0) return const [];
    parts.add(value);
  }
  return parts;
}

/// True when [candidate] is a higher release than [current].
bool isNewerVersion(String candidate, String current) {
  final next = versionParts(candidate);
  final now = versionParts(current);
  if (next.isEmpty || now.isEmpty) return false;
  final length = next.length > now.length ? next.length : now.length;
  for (var i = 0; i < length; i++) {
    final left = i < next.length ? next[i] : 0;
    final right = i < now.length ? now[i] : 0;
    if (left != right) return left > right;
  }
  return false;
}

ReleaseAsset? pickAsset(Iterable<ReleaseAsset> assets, String platform) {
  final wanted = updateAssetNames[platform];
  if (wanted == null) return null;
  for (final asset in assets) {
    if (asset.name == wanted) return asset;
  }
  return null;
}

bool shouldPromptUpdate(String version, String? skipped) => skipped != version;

bool shouldAutoCheck(DateTime? lastChecked, DateTime now) {
  if (lastChecked == null) return true;
  return now.difference(lastChecked) >= const Duration(hours: 24);
}

AvailableUpdate? interpretRelease(
  Object? body, {
  required String current,
  required String platform,
}) {
  if (body is! Map) return null;
  if (body['draft'] == true || body['prerelease'] == true) return null;
  final tag = (body['tag_name'] ?? '').toString();
  final parts = versionParts(tag);
  if (parts.isEmpty) return null;
  final version = parts.join('.');
  if (!isNewerVersion(version, current)) return null;
  final rawAssets = body['assets'];
  if (rawAssets is! List) return null;
  final assets = <ReleaseAsset>[];
  for (final item in rawAssets) {
    if (item is! Map) continue;
    final name = (item['name'] ?? '').toString();
    final url = (item['browser_download_url'] ?? '').toString();
    if (name.isEmpty || url.isEmpty) continue;
    final size = item['size'];
    assets.add(ReleaseAsset(
      name: name,
      url: url,
      size: size is num ? size.toInt() : null,
    ));
  }
  final picked = pickAsset(assets, platform);
  if (picked == null) return null;
  return AvailableUpdate(
    version: version,
    assetName: picked.name,
    url: picked.url,
    size: picked.size,
  );
}

/// Remembers the last check and a version the user asked to see later.
class UpdateStore {
  UpdateStore(this.serviceFile);

  final File serviceFile;

  static const skippedKey = 'update_skipped';
  static const checkedKey = 'update_checked_at';

  Future<String?> skippedVersion() async {
    final data = await _read();
    final value = data[skippedKey];
    if (value is String && value.trim().isNotEmpty) return value.trim();
    return null;
  }

  Future<DateTime?> lastChecked() async {
    final data = await _read();
    final value = data[checkedKey];
    if (value is! String || value.isEmpty) return null;
    return DateTime.tryParse(value);
  }

  Future<void> rememberSkip(String version) async {
    final data = await _read();
    data[skippedKey] = version;
    await _write(data);
  }

  Future<void> rememberCheck(DateTime when) async {
    final data = await _read();
    data[checkedKey] = when.toUtc().toIso8601String();
    await _write(data);
  }

  Future<Map<String, dynamic>> _read() async {
    if (!serviceFile.existsSync()) return {};
    try {
      final json = jsonDecode(await serviceFile.readAsString());
      if (json is Map<String, dynamic>) return json;
      if (json is Map) return Map<String, dynamic>.from(json);
    } catch (_) {}
    return {};
  }

  Future<void> _write(Map<String, dynamic> data) async {
    await serviceFile.parent.create(recursive: true);
    await serviceFile.writeAsString('${const JsonEncoder.withIndent('  ').convert(data)}\n');
  }
}

Future<AvailableUpdate?> fetchLatestRelease({
  HttpClient? client,
  String repo = updateRepo,
  required String current,
  required String platform,
}) async {
  final ownClient = client == null;
  final http = client ?? HttpClient();
  http.userAgent = 'NeuraEC';
  http.connectionTimeout = const Duration(seconds: 20);
  try {
    final request = await http.getUrl(Uri.parse('https://api.github.com/repos/$repo/releases/latest'));
    request.headers.set(HttpHeaders.userAgentHeader, 'NeuraEC');
    request.headers.set(HttpHeaders.acceptHeader, 'application/vnd.github+json');
    final response = await request.close().timeout(const Duration(seconds: 20));
    if (response.statusCode != HttpStatus.ok) {
      await response.drain<void>();
      throw HttpException('github ${response.statusCode}');
    }
    final text = await response.transform(utf8.decoder).join().timeout(const Duration(seconds: 20));
    final body = jsonDecode(text);
    return interpretRelease(body, current: current, platform: platform);
  } finally {
    if (ownClient) http.close(force: true);
  }
}

Future<File> downloadRelease(
  AvailableUpdate update,
  Directory directory, {
  required void Function(int received, int? total) onProgress,
  required bool Function() isCancelled,
  HttpClient? client,
}) async {
  final ownClient = client == null;
  final http = client ?? HttpClient();
  http.userAgent = 'NeuraEC';
  http.connectionTimeout = const Duration(seconds: 30);
  IOSink? sink;
  await directory.create(recursive: true);
  final part = File('${directory.path}${Platform.pathSeparator}${update.assetName}.part');
  try {
    final request = await http.getUrl(Uri.parse(update.url));
    request.followRedirects = true;
    request.maxRedirects = 5;
    request.headers.set(HttpHeaders.userAgentHeader, 'NeuraEC');
    final response = await request.close();
    if (response.statusCode != HttpStatus.ok) {
      await response.drain<void>();
      throw HttpException('download failed (${response.statusCode})');
    }
    final total = response.contentLength > 0 ? response.contentLength : update.size;
    var received = 0;
    sink = part.openWrite();
    await for (final chunk in response) {
      if (isCancelled()) throw const DownloadCancelled();
      sink.add(chunk);
      received += chunk.length;
      onProgress(received, total);
    }
    await sink.flush();
    await sink.close();
    sink = null;
    if (isCancelled()) throw const DownloadCancelled();
    final dest = File('${directory.path}${Platform.pathSeparator}${update.assetName}');
    if (dest.existsSync()) await dest.delete();
    return part.rename(dest.path);
  } catch (error) {
    try {
      await sink?.close();
    } catch (_) {}
    if (part.existsSync()) {
      try {
        await part.delete();
      } catch (_) {}
    }
    rethrow;
  } finally {
    if (ownClient) http.close(force: true);
  }
}

Future<void> revealDownload(File file) async {
  if (Platform.isMacOS) {
    await Process.run('open', [file.path]);
  } else if (Platform.isWindows) {
    await Process.run('explorer', [file.path]);
  } else if (Platform.isLinux) {
    await Process.run('xdg-open', [file.path]);
  }
}
