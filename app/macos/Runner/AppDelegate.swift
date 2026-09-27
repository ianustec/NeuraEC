import Cocoa
import FlutterMacOS

@main
class AppDelegate: FlutterAppDelegate {
  override func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
    return false
  }

  override func applicationSupportsSecureRestorableState(_ app: NSApplication) -> Bool {
    return true
  }
}

/// Icona nella barra dei menu. In quello stato l'app non sta nel Dock.
final class MenuBarController: NSObject {
  static let shared = MenuBarController()

  private var statusItem: NSStatusItem?
  private weak var window: NSWindow?
  private var stats: [String: String] = [:]
  var channel: FlutterMethodChannel?

  func attach(window: NSWindow) {
    self.window = window
  }

  func reduce() {
    window?.orderOut(nil)
    NSApp.setActivationPolicy(.accessory)
    if statusItem == nil {
      statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
    }
    applyIcon()
    rebuildMenu()
  }

  func show() {
    statusItem.map { NSStatusBar.system.removeStatusItem($0) }
    statusItem = nil
    NSApp.setActivationPolicy(.regular)
    window?.makeKeyAndOrderFront(nil)
    NSApp.activate(ignoringOtherApps: true)
  }

  func update(_ values: [String: String]) {
    stats = values
    applyIcon()
    if statusItem != nil {
      rebuildMenu()
    }
  }

  private var serviceOn: Bool { stats["service"] == "on" }

  private func applyIcon() {
    let symbol = serviceOn ? "n.circle.fill" : "n.circle"
    guard let image = NSImage(systemSymbolName: symbol, accessibilityDescription: "NEURA") else { return }
    image.isTemplate = true
    statusItem?.button?.image = image
  }

  private func rebuildMenu() {
    let menu = NSMenu()
    // Senza questo, AppKit ignora isEnabled e riaccende ogni voce che ha un'azione.
    menu.autoenablesItems = false
    let account = stats["account"].flatMap { $0.isEmpty ? nil : $0 } ?? "NEURA"
    menu.addItem(disabled(account))
    menu.addItem(disabled("\(label("menuClassified", "Classificate")): \(stats["waiting"] ?? "0")"))
    menu.addItem(disabled("\(label("menuPer100", "Correzioni / 100")): \(stats["per100"] ?? "0.00")"))
    menu.addItem(disabled("\(label("menuRight", "Nel posto giusto")): \(stats["accuracy"] ?? "—")"))
    menu.addItem(.separator())
    let status = NSMenuItem(
      title: serviceOn ? label("menuActive", "Classificazione attiva") : label("menuPaused", "Classificazione in pausa"),
      action: nil,
      keyEquivalent: ""
    )
    status.state = serviceOn ? .on : .off
    status.isEnabled = false
    menu.addItem(status)
    let start = NSMenuItem(title: label("menuStart", "Avvia classificazione"), action: #selector(startService), keyEquivalent: "")
    start.target = self
    start.isEnabled = !serviceOn
    menu.addItem(start)
    let stop = NSMenuItem(title: label("menuPause", "Metti in pausa"), action: #selector(stopService), keyEquivalent: "")
    stop.target = self
    stop.isEnabled = serviceOn
    menu.addItem(stop)
    menu.addItem(.separator())
    let open = NSMenuItem(title: label("menuOpen", "Apri NEURA"), action: #selector(openApp), keyEquivalent: "")
    open.target = self
    menu.addItem(open)
    let quit = NSMenuItem(title: label("menuQuit", "Esci"), action: #selector(quitApp), keyEquivalent: "q")
    quit.target = self
    menu.addItem(quit)
    statusItem?.menu = menu
  }

  private func label(_ key: String, _ fallback: String) -> String {
    let value = stats[key]
    if let value, !value.isEmpty { return value }
    return fallback
  }

  private func disabled(_ title: String) -> NSMenuItem {
    let item = NSMenuItem(title: title, action: nil, keyEquivalent: "")
    item.isEnabled = false
    return item
  }

  @objc private func startService() {
    channel?.invokeMethod("setService", arguments: true)
  }

  @objc private func stopService() {
    channel?.invokeMethod("setService", arguments: false)
  }

  @objc private func openApp() {
    show()
  }

  @objc private func quitApp() {
    NSApp.terminate(nil)
  }
}
