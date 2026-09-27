#include "flutter_window.h"

#include <optional>
#include <shellapi.h>

#include "flutter/generated_plugin_registrant.h"
#include "resource.h"

namespace {

constexpr UINT kTrayMessage = WM_APP + 1;
constexpr UINT kTrayId = 1;
constexpr UINT kCmdOpen = 1;
constexpr UINT kCmdStart = 2;
constexpr UINT kCmdStop = 3;
constexpr UINT kCmdQuit = 4;

std::string ReadArg(const flutter::EncodableMap& map, const std::string& key) {
  auto it = map.find(flutter::EncodableValue(key));
  if (it == map.end()) {
    return "";
  }
  if (const auto* value = std::get_if<std::string>(&it->second)) {
    return *value;
  }
  return "";
}

}  // namespace

FlutterWindow::FlutterWindow(const flutter::DartProject& project)
    : project_(project) {}

FlutterWindow::~FlutterWindow() {}

bool FlutterWindow::OnCreate() {
  if (!Win32Window::OnCreate()) {
    return false;
  }

  RECT frame = GetClientArea();

  flutter_controller_ = std::make_unique<flutter::FlutterViewController>(
      frame.right - frame.left, frame.bottom - frame.top, project_);
  if (!flutter_controller_->engine() || !flutter_controller_->view()) {
    return false;
  }
  RegisterPlugins(flutter_controller_->engine());
  SetChildContent(flutter_controller_->view()->GetNativeWindow());

  channel_ = std::make_unique<flutter::MethodChannel<flutter::EncodableValue>>(
      flutter_controller_->engine()->messenger(), "it.bentho.neura/menubar",
      &flutter::StandardMethodCodec::GetInstance());
  channel_->SetMethodCallHandler(
      [this](const flutter::MethodCall<flutter::EncodableValue>& call,
             std::unique_ptr<flutter::MethodResult<flutter::EncodableValue>> result) {
        if (call.method_name() == "reduce") {
          ReduceToTray();
          result->Success();
        } else if (call.method_name() == "show") {
          ShowFromTray();
          result->Success();
        } else if (call.method_name() == "update") {
          if (const auto* args = std::get_if<flutter::EncodableMap>(call.arguments())) {
            account_ = ReadArg(*args, "account");
            waiting_ = ReadArg(*args, "waiting");
            per100_ = ReadArg(*args, "per100");
            accuracy_ = ReadArg(*args, "accuracy");
            service_ = ReadArg(*args, "service");
            auto take = [&](const char* key, std::string& dest) {
              const auto value = ReadArg(*args, key);
              if (!value.empty()) dest = value;
            };
            take("menuClassified", menu_classified_);
            take("menuPer100", menu_per100_);
            take("menuRight", menu_right_);
            take("menuActive", menu_active_);
            take("menuPaused", menu_paused_);
            take("menuStart", menu_start_);
            take("menuPause", menu_pause_);
            take("menuOpen", menu_open_);
            take("menuQuit", menu_quit_);
            if (account_.empty()) account_ = "NEURA";
          }
          result->Success();
        } else {
          result->NotImplemented();
        }
      });

  flutter_controller_->engine()->SetNextFrameCallback([&]() { this->Show(); });
  flutter_controller_->ForceRedraw();

  return true;
}

void FlutterWindow::OnDestroy() {
  RemoveTrayIcon();
  channel_ = nullptr;
  if (flutter_controller_) {
    flutter_controller_ = nullptr;
  }

  Win32Window::OnDestroy();
}

std::wstring FlutterWindow::Wide(const std::string& text) const {
  if (text.empty()) return L"";
  int size = MultiByteToWideChar(CP_UTF8, 0, text.c_str(), -1, nullptr, 0);
  std::wstring out(size > 0 ? static_cast<size_t>(size - 1) : 0, L'\0');
  if (size > 1) {
    MultiByteToWideChar(CP_UTF8, 0, text.c_str(), -1, out.data(), size);
  }
  return out;
}

void FlutterWindow::ReduceToTray() {
  HWND hwnd = GetHandle();
  if (!hwnd) return;
  if (!tray_added_) {
    NOTIFYICONDATAW icon{};
    icon.cbSize = sizeof(icon);
    icon.hWnd = hwnd;
    icon.uID = kTrayId;
    icon.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP;
    icon.uCallbackMessage = kTrayMessage;
    icon.hIcon = LoadIcon(GetModuleHandle(nullptr), MAKEINTRESOURCE(IDI_APP_ICON));
    if (!icon.hIcon) {
      icon.hIcon = LoadIcon(nullptr, IDI_APPLICATION);
    }
    wcscpy_s(icon.szTip, L"NeuraEC");
    Shell_NotifyIconW(NIM_ADD, &icon);
    tray_added_ = true;
  }
  ShowWindow(hwnd, SW_HIDE);
}

void FlutterWindow::ShowFromTray() {
  RemoveTrayIcon();
  HWND hwnd = GetHandle();
  if (!hwnd) return;
  ShowWindow(hwnd, SW_SHOW);
  ShowWindow(hwnd, SW_RESTORE);
  SetForegroundWindow(hwnd);
}

void FlutterWindow::RemoveTrayIcon() {
  if (!tray_added_) return;
  NOTIFYICONDATAW icon{};
  icon.cbSize = sizeof(icon);
  icon.hWnd = GetHandle();
  icon.uID = kTrayId;
  Shell_NotifyIconW(NIM_DELETE, &icon);
  tray_added_ = false;
}

void FlutterWindow::ShowTrayMenu() {
  HWND hwnd = GetHandle();
  if (!hwnd) return;
  const bool on = service_ == "on";
  HMENU menu = CreatePopupMenu();
  AppendMenuW(menu, MF_STRING | MF_GRAYED, 0, Wide(account_).c_str());
  AppendMenuW(menu, MF_STRING | MF_GRAYED, 0, Wide(menu_classified_ + ": " + waiting_).c_str());
  AppendMenuW(menu, MF_STRING | MF_GRAYED, 0, Wide(menu_per100_ + ": " + per100_).c_str());
  AppendMenuW(menu, MF_STRING | MF_GRAYED, 0, Wide(menu_right_ + ": " + accuracy_).c_str());
  AppendMenuW(menu, MF_SEPARATOR, 0, nullptr);
  AppendMenuW(menu, MF_STRING | MF_GRAYED, 0, Wide(on ? menu_active_ : menu_paused_).c_str());
  AppendMenuW(menu, MF_STRING | (on ? MF_GRAYED : MF_ENABLED), kCmdStart, Wide(menu_start_).c_str());
  AppendMenuW(menu, MF_STRING | (on ? MF_ENABLED : MF_GRAYED), kCmdStop, Wide(menu_pause_).c_str());
  AppendMenuW(menu, MF_SEPARATOR, 0, nullptr);
  AppendMenuW(menu, MF_STRING, kCmdOpen, Wide(menu_open_).c_str());
  AppendMenuW(menu, MF_STRING, kCmdQuit, Wide(menu_quit_).c_str());

  POINT point;
  GetCursorPos(&point);
  SetForegroundWindow(hwnd);
  TrackPopupMenu(menu, TPM_RIGHTALIGN | TPM_BOTTOMALIGN, point.x, point.y, 0, hwnd, nullptr);
  PostMessage(hwnd, WM_NULL, 0, 0);
  DestroyMenu(menu);
}

LRESULT
FlutterWindow::MessageHandler(HWND hwnd, UINT const message, WPARAM const wparam,
                              LPARAM const lparam) noexcept {
  if (message == WM_SYSCOMMAND && (wparam & 0xFFF0) == SC_MINIMIZE) {
    ReduceToTray();
    return 0;
  }

  if (message == kTrayMessage) {
    if (lparam == WM_LBUTTONUP || lparam == WM_LBUTTONDBLCLK) {
      ShowFromTray();
      return 0;
    }
    if (lparam == WM_RBUTTONUP) {
      ShowTrayMenu();
      return 0;
    }
  }

  if (message == WM_COMMAND) {
    switch (LOWORD(wparam)) {
      case kCmdOpen:
        ShowFromTray();
        return 0;
      case kCmdStart:
        if (channel_) {
          channel_->InvokeMethod("setService", std::make_unique<flutter::EncodableValue>(true));
        }
        return 0;
      case kCmdStop:
        if (channel_) {
          channel_->InvokeMethod("setService", std::make_unique<flutter::EncodableValue>(false));
        }
        return 0;
      case kCmdQuit:
        RemoveTrayIcon();
        PostQuitMessage(0);
        return 0;
    }
  }

  if (flutter_controller_) {
    std::optional<LRESULT> result = flutter_controller_->HandleTopLevelWindowProc(
        hwnd, message, wparam, lparam);
    if (result) {
      return *result;
    }
  }

  switch (message) {
    case WM_FONTCHANGE:
      flutter_controller_->engine()->ReloadSystemFonts();
      break;
  }

  return Win32Window::MessageHandler(hwnd, message, wparam, lparam);
}
