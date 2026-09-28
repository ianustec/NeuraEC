import Cocoa
import FlutterMacOS

class MainFlutterWindow: NSWindow, NSWindowDelegate {
  override func awakeFromNib() {
    let flutterViewController = FlutterViewController()
    let windowFrame = self.frame
    self.contentViewController = flutterViewController
    self.setFrame(windowFrame, display: true)

    RegisterGeneratedPlugins(registry: flutterViewController)

    let channel = FlutterMethodChannel(
      name: "it.bentho.neura/menubar",
      binaryMessenger: flutterViewController.engine.binaryMessenger
    )
    MenuBarController.shared.attach(window: self)
    MenuBarController.shared.channel = channel
    channel.setMethodCallHandler { call, result in
      switch call.method {
      case "reduce":
        MenuBarController.shared.reduce()
        result(nil)
      case "show":
        MenuBarController.shared.show()
        result(nil)
      case "update":
        MenuBarController.shared.update((call.arguments as? [String: String]) ?? [:])
        result(nil)
      default:
        result(FlutterMethodNotImplemented)
      }
    }

    super.awakeFromNib()
    self.delegate = self
    self.isRestorable = false
    self.title = "NeuraEC"
    // La finestra non ha una barra bianca sua: i pallini stanno sullo sfondo dell'app.
    self.titleVisibility = .hidden
    self.titlebarAppearsTransparent = true
    self.titlebarSeparatorStyle = .none
    self.styleMask.insert(.fullSizeContentView)
    self.isMovableByWindowBackground = true
    self.backgroundColor = NSColor(srgbRed: 0xF5 / 255, green: 0xF7 / 255, blue: 0xFC / 255, alpha: 1)
    resizeToThreeQuarters()
    // I pallini standard nascono dopo lo style mask. Il giallo va reindirizzato
    // a mano: su questo macOS non passa da windowShouldMiniaturize.
    DispatchQueue.main.async { [weak self] in
      self?.routeMinimizeToMenuBar()
    }
  }

  /// Il pallino giallo, Comando-M e Finestra → Contrai. Non chiamare super:
  /// super mette la finestra nel Dock.
  @objc func hideToMenuBar(_ sender: Any?) {
    MenuBarController.shared.reduce()
  }

  override func performMiniaturize(_ sender: Any?) {
    hideToMenuBar(sender)
  }

  override func miniaturize(_ sender: Any?) {
    hideToMenuBar(sender)
  }

  private func routeMinimizeToMenuBar() {
    guard let button = standardWindowButton(.miniaturizeButton) else { return }
    button.target = self
    button.action = #selector(hideToMenuBar(_:))
  }

  private func resizeToThreeQuarters() {
    guard let visible = (self.screen ?? NSScreen.main)?.visibleFrame else { return }
    let width = visible.width * 0.75
    let height = visible.height * 0.75
    let frame = NSRect(
      x: visible.origin.x + (visible.width - width) / 2,
      y: visible.origin.y + (visible.height - height) / 2,
      width: width,
      height: height
    )
    self.setFrame(frame, display: true)
    self.minSize = NSSize(width: 960, height: 640)
  }

  func windowShouldClose(_ sender: NSWindow) -> Bool {
    MenuBarController.shared.reduce()
    return false
  }

  /// Il pallino giallo e il menu Finestra → Contrai. Senza questo la finestra
  /// finisce nel Dock; deve sparire come il tasto in-app, solo nella barra.
  func windowShouldMiniaturize(_ sender: NSWindow) -> Bool {
    MenuBarController.shared.reduce()
    return false
  }
}
