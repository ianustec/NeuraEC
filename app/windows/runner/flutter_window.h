#ifndef RUNNER_FLUTTER_WINDOW_H_
#define RUNNER_FLUTTER_WINDOW_H_

#include <flutter/dart_project.h>
#include <flutter/flutter_view_controller.h>
#include <flutter/method_channel.h>
#include <flutter/standard_method_codec.h>

#include <memory>
#include <string>

#include "win32_window.h"

// A window that does nothing but host a Flutter view.
class FlutterWindow : public Win32Window {
 public:
  // Creates a new FlutterWindow hosting a Flutter view running |project|.
  explicit FlutterWindow(const flutter::DartProject& project);
  virtual ~FlutterWindow();

 protected:
  // Win32Window:
  bool OnCreate() override;
  void OnDestroy() override;
  LRESULT MessageHandler(HWND window, UINT const message, WPARAM const wparam,
                         LPARAM const lparam) noexcept override;

 private:
  void ReduceToTray();
  void ShowFromTray();
  void ShowTrayMenu();
  void RemoveTrayIcon();
  std::wstring Wide(const std::string& text) const;

  flutter::DartProject project_;

  std::unique_ptr<flutter::FlutterViewController> flutter_controller_;
  std::unique_ptr<flutter::MethodChannel<flutter::EncodableValue>> channel_;

  bool tray_added_ = false;
  std::string account_ = "NEURA";
  std::string waiting_ = "0";
  std::string per100_ = "0.00";
  std::string accuracy_ = "0.000";
  std::string service_ = "off";
  std::string menu_classified_ = "Classificate";
  std::string menu_per100_ = "Correzioni / 100";
  std::string menu_right_ = "Nel posto giusto";
  std::string menu_active_ = "Classificazione attiva";
  std::string menu_paused_ = "Classificazione in pausa";
  std::string menu_start_ = "Avvia classificazione";
  std::string menu_pause_ = "Metti in pausa";
  std::string menu_open_ = "Apri NEURA";
  std::string menu_quit_ = "Esci";
};

#endif  // RUNNER_FLUTTER_WINDOW_H_
