from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PyQt6.QtCore import QEasingCurve, QDateTime, QPropertyAnimation, QRect, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from smart_home import SmartHomeService


BG = "#050608"
PANEL = "#0b0c10"
PANEL_2 = "#101116"
ACCENT = "#ff4545"
ACCENT_SOFT = "rgba(255,69,69,0.12)"
ACCENT_LINE = "rgba(255,69,69,0.22)"
TEXT = "#ffffff"
TEXT_MED = "rgba(255,255,255,0.82)"
TEXT_DIM = "rgba(255,255,255,0.62)"
GREEN = "#35ff75"


@dataclass(frozen=True)
class PlatformRow:
    key: str
    name: str
    available: bool
    auth_fields: list[tuple[str, str, str, bool]]


class ClickableFrame(QFrame):
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


def _panel_style(border_alpha: int = 34) -> str:
    return (
        f"QFrame {{ background: rgba(12,12,14,245); "
        f"border: 1px solid rgba(255,69,69,{border_alpha}); border-radius: 18px; }}"
    )


def _soft_button_style() -> str:
    return (
        f"QPushButton {{ background: rgba(255,255,255,0.04); color: {TEXT}; "
        "border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 0 12px; }}"
        f"QPushButton:hover {{ border: 1px solid {ACCENT}; }}"
    )


class AddDeviceDialog(QDialog):
    def __init__(self, service: SmartHomeService, parent=None):
        super().__init__(parent)
        self._service = service
        self._provider_key: str | None = None
        self._provider_label = ""
        self._preview: dict[str, Any] = {}
        self._result: dict[str, Any] = {}
        self._fields: dict[str, QLineEdit] = {}
        self._checks: list[tuple[str, QCheckBox]] = []
        self._platform_buttons: list[QPushButton] = []

        self.setWindowTitle("Add Device")
        self.setModal(True)
        self.setMinimumSize(780, 620)
        self.setStyleSheet(
            f"""
            QDialog {{ background: {BG}; color: {TEXT}; }}
            QLabel {{ background: transparent; }}
            QLineEdit, QComboBox {{
                background: rgba(255,255,255,0.04);
                color: {TEXT};
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
                min-height: 34px;
                padding: 0 10px;
            }}
            QScrollArea {{ background: transparent; border: none; }}
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("ADD DEVICE")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Black))
        title.setStyleSheet(f"color: {TEXT}; letter-spacing: 2px;")
        sub = QLabel("Choose a platform, authenticate, scan, and save your devices locally.")
        sub.setStyleSheet(f"color: {TEXT_DIM};")
        root.addWidget(title)
        root.addWidget(sub)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_platform_page())
        self._stack.addWidget(self._build_auth_page())
        self._stack.addWidget(self._build_scan_page())
        self._stack.addWidget(self._build_finish_page())
        root.addWidget(self._stack, 1)

        row = QHBoxLayout()
        row.addStretch(1)
        self._back_btn = QPushButton("Back")
        self._next_btn = QPushButton("Next")
        self._cancel_btn = QPushButton("Cancel")
        for btn in (self._back_btn, self._next_btn, self._cancel_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(36)
            btn.setStyleSheet(_soft_button_style())
        self._back_btn.clicked.connect(self._go_back)
        self._next_btn.clicked.connect(self._go_next)
        self._cancel_btn.clicked.connect(self.reject)
        row.addWidget(self._back_btn)
        row.addWidget(self._next_btn)
        row.addWidget(self._cancel_btn)
        root.addLayout(row)
        self._sync_buttons()

    def result_payload(self) -> dict[str, Any]:
        return dict(self._result)

    def _card(self, title: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(_panel_style(40))
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)
        lbl = QLabel(title)
        lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {TEXT};")
        lay.addWidget(lbl)
        return frame

    def _build_platform_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        lay.addWidget(self._card("Step 1: Choose Platform"))

        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        for idx, platform in enumerate(self._platforms()):
            btn = QPushButton(platform.name + ("" if platform.available else " (Coming Soon)"))
            btn.setCheckable(True)
            btn.setEnabled(platform.available)
            btn.setMinimumHeight(46)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"""
                QPushButton {{
                    text-align: left;
                    background: rgba(255,255,255,0.03);
                    color: {TEXT};
                    border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 12px;
                    padding: 8px 12px;
                }}
                QPushButton:checked {{
                    background: {ACCENT_SOFT};
                    border: 1px solid {ACCENT};
                }}
                """
            )
            btn.clicked.connect(lambda _=False, key=platform.key, label=platform.name: self._choose_provider(key, label))
            self._platform_buttons.append(btn)
            grid.addWidget(btn, idx // 2, idx % 2)
        lay.addWidget(grid_host)
        return page

    def _build_auth_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        lay.addWidget(self._card("Step 2: Authenticate"))
        self._auth_desc = QLabel("Select a platform to build the right authentication form.")
        self._auth_desc.setStyleSheet(f"color: {TEXT_DIM};")
        lay.addWidget(self._auth_desc)
        self._auth_form_host = QFrame()
        self._auth_form_host.setStyleSheet("background: transparent;")
        self._auth_form = QFormLayout(self._auth_form_host)
        self._auth_form.setContentsMargins(12, 0, 12, 12)
        self._auth_form.setVerticalSpacing(10)
        lay.addWidget(self._auth_form_host)
        return page

    def _build_scan_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        lay.addWidget(self._card("Step 3: Scan"))
        self._scan_label = QLabel("Searching for devices...")
        self._scan_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self._scan_label.setStyleSheet(f"color: {TEXT};")
        lay.addWidget(self._scan_label)
        self._scan_bar = QProgressBar()
        self._scan_bar.setRange(0, 100)
        self._scan_bar.setValue(12)
        self._scan_bar.setTextVisible(False)
        self._scan_bar.setFixedHeight(10)
        self._scan_bar.setStyleSheet(
            f"QProgressBar {{ background: rgba(255,255,255,0.05); border: none; border-radius: 4px; }} "
            f"QProgressBar::chunk {{ background: {ACCENT}; border-radius: 4px; }}"
        )
        lay.addWidget(self._scan_bar)
        self._scan_scroll = QScrollArea()
        self._scan_scroll.setWidgetResizable(True)
        self._scan_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scan_host = QWidget()
        self._scan_host.setStyleSheet("background: transparent;")
        self._scan_list = QVBoxLayout(self._scan_host)
        self._scan_list.setSpacing(10)
        self._scan_list.addStretch(1)
        self._scan_scroll.setWidget(self._scan_host)
        lay.addWidget(self._scan_scroll, 1)
        return page

    def _build_finish_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        lay.addWidget(self._card("Step 4: Finish"))
        self._finish_summary = QLabel("")
        self._finish_summary.setWordWrap(True)
        self._finish_summary.setStyleSheet(f"color: {TEXT_MED};")
        lay.addWidget(self._finish_summary)
        return page

    def _platforms(self) -> list[PlatformRow]:
        return [
            PlatformRow("atomberg", "Atomberg Home", True, [("api_key", "API Key", "Atomberg developer API key", False), ("refresh_token", "Refresh Token", "Atomberg refresh token", True)]),
            PlatformRow("kasa", "TP-Link Kasa", True, [("host", "Device IP / Host", "Optional - leave empty to scan the network", False), ("username", "Username", "Optional cloud username", False), ("password", "Password", "Optional cloud password", True)]),
        ]

    def _choose_provider(self, key: str, label: str):
        self._provider_key = key
        self._provider_label = label
        for btn in self._platform_buttons:
            btn.setChecked(btn.text().startswith(label))
        self._build_auth_form()
        self._stack.setCurrentIndex(1)
        self._sync_buttons()

    def _build_auth_form(self):
        while self._auth_form.count():
            item = self._auth_form.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._fields.clear()
        if not self._provider_key:
            self._auth_desc.setText("Select a platform to build the right authentication form.")
            return
        self._auth_desc.setText(f"Authenticate {self._provider_label}. Credentials are stored locally and encrypted.")
        for key, label, placeholder, secret in next((p.auth_fields for p in self._platforms() if p.key == self._provider_key), []):
            edit = QLineEdit()
            edit.setPlaceholderText(placeholder)
            if secret:
                edit.setEchoMode(QLineEdit.EchoMode.Password)
            self._fields[key] = edit
            self._auth_form.addRow(label, edit)
        self._account_label = QLineEdit()
        self._account_label.setPlaceholderText("Example: Home, Suryaansh, Bedroom Hub")
        self._auth_form.addRow("Device label", self._account_label)

    def _build_scan_results(self):
        while self._scan_list.count():
            item = self._scan_list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._checks.clear()
        if not self._preview:
            self._scan_list.addWidget(QLabel("No devices discovered."))
            self._scan_list.addStretch(1)
            return
        for device in self._preview.get("devices", []):
            box = QCheckBox(f"{device['name']}  •  {device.get('manufacturer', '')}")
            box.setChecked(True)
            box.setStyleSheet(f"QCheckBox {{ color: {TEXT}; padding: 10px; }}")
            self._scan_list.addWidget(box)
            self._checks.append((str(device["external_id"]), box))
        self._scan_list.addStretch(1)

    def _go_next(self):
        idx = self._stack.currentIndex()
        if idx == 0:
            if not self._provider_key:
                return
            self._stack.setCurrentIndex(1)
        elif idx == 1:
            if not self._provider_key:
                return
            credentials = {k: e.text().strip() for k, e in self._fields.items()}
            try:
                self._preview = self._service.preview_discovery(self._provider_key, credentials)
            except Exception as exc:
                self._auth_desc.setText(f"Authentication failed: {exc}")
                return
            self._scan_bar.setValue(55)
            self._scan_label.setText("Discovering devices...")
            self._build_scan_results()
            self._stack.setCurrentIndex(2)
        elif idx == 2:
            selected = [ext_id for ext_id, check in self._checks if check.isChecked()]
            self._result = {
                "provider_key": self._provider_key,
                "account_label": self._account_label.text().strip() or self._provider_label,
                "credentials": {k: e.text().strip() for k, e in self._fields.items()},
                "selected_external_ids": selected,
            }
            self._finish_summary.setText(
                f"{len(selected)} device(s) selected from {self._provider_label}.\nConnected devices are saved locally and will appear under MY DEVICES."
            )
            self._stack.setCurrentIndex(3)
        else:
            self.accept()
        self._sync_buttons()

    def _go_back(self):
        idx = self._stack.currentIndex()
        if idx > 0:
            self._stack.setCurrentIndex(idx - 1)
        self._sync_buttons()

    def _sync_buttons(self):
        idx = self._stack.currentIndex()
        self._back_btn.setEnabled(idx > 0)
        self._next_btn.setText("Connect" if idx == 2 else "Next" if idx < 2 else "Finish")
        self._next_btn.setEnabled(True if idx != 0 else bool(self._provider_key))


class _DeviceTile(ClickableFrame):
    action_requested = pyqtSignal(str, str, dict)
    select_requested = pyqtSignal(str)

    def __init__(self, device: dict[str, Any], parent=None):
        super().__init__(parent)
        self.device = device
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(_panel_style(32))
        self.setMinimumHeight(250)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        top = QHBoxLayout()
        badge = QLabel(self._glyph(str(device.get("device_type", "device"))))
        badge.setFixedSize(56, 56)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        badge.setStyleSheet(f"background: {ACCENT_SOFT}; color: {TEXT}; border: 1px solid {ACCENT_LINE}; border-radius: 28px;")
        top.addWidget(badge)
        meta = QVBoxLayout()
        name = QLabel(str(device.get("name", "Device")))
        name.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        name.setStyleSheet(f"color: {TEXT};")
        manufacturer = QLabel(str(device.get("manufacturer", "")))
        manufacturer.setStyleSheet(f"color: {TEXT_DIM};")
        meta.addWidget(name)
        meta.addWidget(manufacturer)
        top.addLayout(meta, 1)
        self._power_chip = QLabel("ON" if device.get("is_on") else "OFF")
        self._power_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._power_chip.setStyleSheet(f"color: {'#35ff75' if device.get('is_on') else TEXT_DIM}; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 5px 10px;")
        top.addWidget(self._power_chip)
        lay.addLayout(top)

        self._detail_lbl = QLabel("")
        self._detail_lbl.setWordWrap(True)
        self._detail_lbl.setStyleSheet(f"color: {TEXT_MED};")
        lay.addWidget(self._detail_lbl)

        self._control_area = QVBoxLayout()
        self._control_area.setSpacing(8)
        lay.addLayout(self._control_area)
        self._build_controls()

    def _glyph(self, kind: str) -> str:
        return {"fan": "F", "light": "L", "ac": "A", "tv": "TV", "plug": "P", "sensor": "S", "curtain": "C", "vacuum": "V"}.get(kind, "D")

    def _chip_style(self) -> str:
        return f"QPushButton {{ background: rgba(255,255,255,0.03); color: {TEXT}; border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 0 12px; }} QPushButton:hover {{ border: 1px solid {ACCENT}; }}"

    def _make_slider(self, minv: int, maxv: int, value: int) -> QSlider:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minv, maxv)
        slider.setValue(value)
        slider.setStyleSheet(f"QSlider::groove:horizontal {{ background: rgba(255,255,255,0.08); height: 6px; border-radius: 3px; }} QSlider::handle:horizontal {{ background: {ACCENT}; width: 18px; margin: -6px 0; border-radius: 9px; }}")
        return slider

    def _build_controls(self):
        kind = str(self.device.get("device_type", "device"))
        self._detail_lbl.setText({
            "fan": "Speed controls, sleep mode, and timer.",
            "light": "Brightness and color controls.",
            "ac": "Temperature and mode controls.",
            "tv": "Volume, mute, and input controls.",
            "plug": "Power control and live status.",
        }.get(kind, "Primary controls available."))
        row = QHBoxLayout()
        self._power_btn = QPushButton("Power")
        self._power_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._power_btn.setFixedHeight(34)
        self._power_btn.clicked.connect(lambda: self.action_requested.emit(str(self.device["id"]), "power", {"is_on": not bool(self.device.get("is_on"))}))
        self._power_btn.setStyleSheet(f"QPushButton {{ background: rgba(255,69,69,0.12); color: {TEXT}; border: 1px solid rgba(255,69,69,0.30); border-radius: 10px; padding: 0 14px; }} QPushButton:hover {{ background: rgba(255,69,69,0.18); }}")
        row.addWidget(self._power_btn)
        if kind == "fan":
            for value in range(1, 6):
                btn = QPushButton(str(value))
                btn.setFixedSize(34, 34)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda _=False, v=value: self.action_requested.emit(str(self.device["id"]), "speed", {"speed": v}))
                btn.setStyleSheet(self._chip_style())
                row.addWidget(btn)
        elif kind == "light":
            self._slider = self._make_slider(0, 100, int(self.device.get("traits", {}).get("brightness", 60)))
            self._slider.valueChanged.connect(lambda value: self.action_requested.emit(str(self.device["id"]), "brightness", {"brightness": value}))
            self._control_area.addWidget(self._slider)
            color_btn = QPushButton("Color")
            color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            color_btn.setFixedHeight(34)
            color_btn.setStyleSheet(self._chip_style())
            row.addWidget(color_btn)
        elif kind == "ac":
            self._slider = self._make_slider(16, 30, int(self.device.get("traits", {}).get("temperature", 24)))
            self._slider.valueChanged.connect(lambda value: self.action_requested.emit(str(self.device["id"]), "temperature", {"temperature": value}))
            self._control_area.addWidget(self._slider)
            mode_btn = QPushButton("Mode")
            mode_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            mode_btn.setFixedHeight(34)
            mode_btn.setStyleSheet(self._chip_style())
            mode_btn.clicked.connect(lambda: self.action_requested.emit(str(self.device["id"]), "mode", {"mode": "Cool"}))
            row.addWidget(mode_btn)
        elif kind == "tv":
            self._slider = self._make_slider(0, 100, int(self.device.get("traits", {}).get("volume", 18)))
            self._slider.valueChanged.connect(lambda value: self.action_requested.emit(str(self.device["id"]), "volume", {"volume": value}))
            self._control_area.addWidget(self._slider)
            mute_btn = QPushButton("Mute")
            mute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            mute_btn.setFixedHeight(34)
            mute_btn.setStyleSheet(self._chip_style())
            input_btn = QPushButton("Input")
            input_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            input_btn.setFixedHeight(34)
            input_btn.setStyleSheet(self._chip_style())
            row.addWidget(mute_btn)
            row.addWidget(input_btn)
        elif kind == "plug":
            usage = QLabel(f"Energy usage: {self.device.get('traits', {}).get('energy_usage', '0W')}")
            usage.setStyleSheet(f"color: {TEXT_DIM};")
            self._control_area.addWidget(usage)
        else:
            self._control_area.addWidget(QLabel("No additional controls."))
        self._control_area.addLayout(row)

    def set_active(self, active: bool):
        self.setStyleSheet(f"QFrame {{ background: {'rgba(255,69,69,0.08)' if active else 'rgba(12,12,14,245)'}; border: 1px solid {'rgba(255,69,69,0.35)' if active else 'rgba(255,69,69,0.16)'}; border-radius: 18px; }}")
        self._power_chip.setStyleSheet(f"color: {'#35ff75' if self.device.get('is_on') else TEXT_DIM}; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 5px 10px;")

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.select_requested.emit(str(self.device["id"]))


class BrahmaHomePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._service = SmartHomeService()
        self._selected_device_id: str | None = None
        self._voice_state = "Listening"
        self._voice_phase = 0
        self._drawer_anim = None
        self._device_tiles: list[_DeviceTile] = []
        self._activity_items: list[dict[str, Any]] = []
        self._device_columns_cached = 0

        self.setObjectName("BrahmaHomePageModern")
        self.setStyleSheet(f"QWidget#BrahmaHomePageModern {{ background: {BG}; }} QScrollArea {{ background: transparent; border: none; }}")

        root = QHBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(14)

        self._main_frame = QFrame()
        self._main_frame.setStyleSheet(_panel_style(40))
        main_lay = QVBoxLayout(self._main_frame)
        main_lay.setContentsMargins(18, 18, 18, 18)
        main_lay.setSpacing(14)
        root.addWidget(self._main_frame, 1)

        self._build_header(main_lay)
        self._build_my_devices(main_lay)

        self._drawer = self._build_drawer()
        self._drawer.hide()

        self._refresh()

    def _section_card(self, title: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(_panel_style(32))
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        head = QLabel(title)
        head.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        head.setStyleSheet(f"color: {TEXT}; letter-spacing: 1px;")
        lay.addWidget(head)
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background: rgba(255,255,255,0.08);")
        lay.addWidget(line)
        return frame

    def _build_header(self, lay: QVBoxLayout):
        row = QHBoxLayout()
        row.setSpacing(12)
        text = QVBoxLayout()
        title = QLabel("BRAHMA HOME")
        title.setFont(QFont("Segoe UI", 24, QFont.Weight.Black))
        title.setStyleSheet(f"color: {TEXT}; letter-spacing: 1px;")
        subtitle = QLabel("Control your smart home with Brahma AI.")
        subtitle.setFont(QFont("Segoe UI", 11))
        subtitle.setStyleSheet(f"color: {TEXT_DIM};")
        text.addWidget(title)
        text.addWidget(subtitle)
        row.addLayout(text, 1)
        self._status_chip = QLabel("  Home Connected\n  Online")
        self._status_chip.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._status_chip.setStyleSheet(f"QLabel {{ background: rgba(12,12,14,235); color: {TEXT}; border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 12px 16px; min-width: 120px; }}")
        row.addWidget(self._status_chip)
        self._voice_button = QPushButton("▮▮")
        self._voice_button.setFixedSize(64, 64)
        self._voice_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._voice_button.setStyleSheet(f"QPushButton {{ background: rgba(12,12,14,235); color: {TEXT}; border: 1px solid rgba(255,255,255,0.10); border-radius: 32px; font-size: 22px; }} QPushButton:hover {{ border: 1px solid {ACCENT}; }}")
        self._voice_button.clicked.connect(self._toggle_voice_mode)
        row.addWidget(self._voice_button)
        lay.addLayout(row)

    def _build_voice_card(self, lay: QVBoxLayout):
        self._voice_frame = QFrame()
        self._voice_frame.setStyleSheet(_panel_style(36))
        vf = QHBoxLayout(self._voice_frame)
        vf.setContentsMargins(18, 16, 18, 16)
        vf.setSpacing(16)
        self._mic_orb = QLabel("🎤")
        self._mic_orb.setFixedSize(86, 86)
        self._mic_orb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._mic_orb.setFont(QFont("Segoe UI", 26))
        self._mic_orb.setStyleSheet(f"QLabel {{ background: rgba(255,69,69,0.12); color: {TEXT}; border: 2px solid rgba(255,69,69,0.55); border-radius: 43px; }}")
        vf.addWidget(self._mic_orb)
        middle = QVBoxLayout()
        self._voice_state_lbl = QLabel("Listening...")
        self._voice_state_lbl.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self._voice_state_lbl.setStyleSheet(f"color: {TEXT};")
        self._voice_cmd_lbl = QLabel('"Turn bedroom fan to speed 4"')
        self._voice_cmd_lbl.setStyleSheet(f"color: {TEXT_MED};")
        middle.addWidget(self._voice_state_lbl)
        middle.addWidget(self._voice_cmd_lbl)
        vf.addLayout(middle, 1)
        self._wave = QHBoxLayout()
        self._wave.setSpacing(3)
        self._wave_bars: list[QFrame] = []
        for _ in range(36):
            bar = QFrame()
            bar.setFixedSize(4, 12)
            bar.setStyleSheet("background: rgba(255,69,69,0.20); border-radius: 2px;")
            self._wave.addWidget(bar, alignment=Qt.AlignmentFlag.AlignVCenter)
            self._wave_bars.append(bar)
        vf.addLayout(self._wave)
        lay.addWidget(self._voice_frame)

    def _build_my_devices(self, lay: QVBoxLayout):
        header = QHBoxLayout()
        title = QLabel("MY DEVICES")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {TEXT}; letter-spacing: 1px;")
        header.addWidget(title)
        header.addStretch(1)
        self._add_btn = QPushButton("+ Add Device")
        self._add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_btn.setFixedHeight(38)
        self._add_btn.setStyleSheet(f"QPushButton {{ background: transparent; color: {TEXT}; border: 1px solid {ACCENT}; border-radius: 12px; padding: 0 14px; }} QPushButton:hover {{ background: rgba(255,69,69,0.10); }}")
        self._add_btn.clicked.connect(self._open_add_device)
        header.addWidget(self._add_btn)
        lay.addLayout(header)

        self._empty_state = QFrame()
        empty_lay = QVBoxLayout(self._empty_state)
        empty_lay.setContentsMargins(28, 32, 28, 32)
        empty_lay.setSpacing(10)
        empty_title = QLabel("No devices added.")
        empty_title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        empty_title.setStyleSheet(f"color: {TEXT};")
        empty_sub = QLabel("Add a device to start controlling your home.")
        empty_sub.setStyleSheet(f"color: {TEXT_DIM};")
        empty_lay.addWidget(empty_title, alignment=Qt.AlignmentFlag.AlignHCenter)
        empty_lay.addWidget(empty_sub, alignment=Qt.AlignmentFlag.AlignHCenter)
        self._empty_add_btn = QPushButton("Add Device")
        self._empty_add_btn.setFixedSize(150, 42)
        self._empty_add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._empty_add_btn.setStyleSheet(f"QPushButton {{ background: rgba(255,69,69,0.12); color: {TEXT}; border: 1px solid {ACCENT}; border-radius: 12px; }} QPushButton:hover {{ background: rgba(255,69,69,0.18); }}")
        self._empty_add_btn.clicked.connect(self._open_add_device)
        empty_lay.addWidget(self._empty_add_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self._empty_state)

        self._device_scroll = QScrollArea()
        self._device_scroll.setWidgetResizable(True)
        self._device_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._device_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._device_content = QWidget()
        self._device_content.setStyleSheet("background: transparent;")
        self._device_grid = QGridLayout(self._device_content)
        self._device_grid.setContentsMargins(0, 0, 0, 0)
        self._device_grid.setHorizontalSpacing(12)
        self._device_grid.setVerticalSpacing(12)
        self._device_scroll.setWidget(self._device_content)
        lay.addWidget(self._device_scroll, 1)

    def _build_voice_control_card(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(_panel_style(32))
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)
        head = QLabel("VOICE CONTROL")
        head.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        head.setStyleSheet(f"color: {TEXT};")
        lay.addWidget(head)
        self._wake_lbl = QLabel("Wake word\nBrahma")
        self._wake_lbl.setStyleSheet(f"color: {TEXT_DIM};")
        lay.addWidget(self._wake_lbl)
        self._voice_state_small = QLabel("Idle")
        self._voice_state_small.setStyleSheet(f"color: {ACCENT}; font-weight: 700;")
        lay.addWidget(self._voice_state_small)
        self._voice_small_wave = QHBoxLayout()
        self._voice_small_wave.setSpacing(3)
        self._voice_small_bars: list[QFrame] = []
        for _ in range(18):
            bar = QFrame()
            bar.setFixedSize(4, 10)
            bar.setStyleSheet("background: rgba(255,69,69,0.20); border-radius: 2px;")
            self._voice_small_wave.addWidget(bar)
            self._voice_small_bars.append(bar)
        lay.addLayout(self._voice_small_wave)
        self._voice_button_big = QPushButton("🎤")
        self._voice_button_big.setFixedSize(84, 84)
        self._voice_button_big.setCursor(Qt.CursorShape.PointingHandCursor)
        self._voice_button_big.setStyleSheet(f"QPushButton {{ background: rgba(255,69,69,0.12); color: {TEXT}; border: 2px solid rgba(255,69,69,0.55); border-radius: 42px; font-size: 28px; }} QPushButton:hover {{ background: rgba(255,69,69,0.18); }}")
        self._voice_button_big.clicked.connect(self._toggle_voice_mode)
        lay.addWidget(self._voice_button_big, alignment=Qt.AlignmentFlag.AlignRight)
        return frame

    def _build_drawer(self) -> QFrame:
        drawer = QFrame(self)
        drawer.setStyleSheet(_panel_style(44))
        drawer.setGeometry(0, 0, 0, 0)
        lay = QVBoxLayout(drawer)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        top = QHBoxLayout()
        title = QLabel("DEVICE DETAILS")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {TEXT};")
        top.addWidget(title)
        top.addStretch(1)
        close_btn = QPushButton("X")
        close_btn.setFixedSize(32, 32)
        close_btn.clicked.connect(self._close_drawer)
        close_btn.setStyleSheet(_soft_button_style())
        top.addWidget(close_btn)
        lay.addLayout(top)
        self._drawer_name = QLabel("")
        self._drawer_name.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self._drawer_name.setStyleSheet(f"color: {TEXT};")
        lay.addWidget(self._drawer_name)
        self._drawer_meta = QLabel("")
        self._drawer_meta.setStyleSheet(f"color: {TEXT_DIM};")
        self._drawer_meta.setWordWrap(True)
        lay.addWidget(self._drawer_meta)
        self._drawer_state = QLabel("")
        self._drawer_state.setStyleSheet(f"color: {TEXT_MED}; font-weight: 700;")
        lay.addWidget(self._drawer_state)
        self._drawer_info = QLabel("")
        self._drawer_info.setWordWrap(True)
        self._drawer_info.setStyleSheet(f"color: {TEXT_MED};")
        lay.addWidget(self._drawer_info)
        self._drawer_actions = QHBoxLayout()
        lay.addLayout(self._drawer_actions)
        return drawer

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._drawer.isVisible():
            width = min(360, max(300, int(self.width() * 0.28)))
            self._drawer.setGeometry(self.width() - width - 12, 12, width, self.height() - 24)
        self._reflow_devices()

    def _device_columns(self) -> int:
        viewport = self._device_scroll.viewport().width() if hasattr(self, "_device_scroll") else 0
        available = max(1, viewport or self.width())
        if available >= 1240:
            return 4
        if available >= 980:
            return 3
        return 2

    def _reflow_devices(self):
        if not hasattr(self, "_device_grid"):
            return
        columns = self._device_columns()
        if columns == self._device_columns_cached:
            return
        self._device_columns_cached = columns
        self._refresh_devices(self._service.list_devices())

    def _animate_drawer(self, open_: bool):
        if self._drawer_anim and self._drawer_anim.state() == QPropertyAnimation.State.Running:
            self._drawer_anim.stop()
        current = self._drawer.geometry()
        width = min(360, max(300, int(self.width() * 0.28)))
        start = QRect(self.width() - 12, 12, 0, self.height() - 24) if not open_ else current
        end = QRect(self.width() - width - 12, 12, width, self.height() - 24) if open_ else QRect(self.width() - 12, 12, 0, self.height() - 24)
        if open_:
            self._drawer.show()
        self._drawer_anim = QPropertyAnimation(self._drawer, b"geometry", self)
        self._drawer_anim.setDuration(260)
        self._drawer_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._drawer_anim.setStartValue(start)
        self._drawer_anim.setEndValue(end)
        if not open_:
            self._drawer_anim.finished.connect(self._drawer.hide)
        self._drawer_anim.start()

    def _open_drawer(self, device: dict[str, Any]):
        self._selected_device_id = str(device.get("id"))
        self._drawer_name.setText(str(device.get("name", "Device")))
        self._drawer_meta.setText(
            f"Manufacturer: {device.get('manufacturer', '')}\nRoom: {device.get('room', '')}\nConnection: Local\nLast Updated: now"
        )
        traits = device.get("traits") or {}
        self._drawer_state.setText(f"Power: {'On' if device.get('is_on') else 'Off'}")
        self._drawer_info.setText(
            f"Firmware: {traits.get('firmware', 'Current')}\nMAC: {traits.get('mac', 'Local')}\nIP: {traits.get('ip', 'Local')}\nBattery: {traits.get('battery', 'N/A')}\nPower Consumption: {traits.get('energy_usage', traits.get('power_usage', 'N/A'))}"
        )
        while self._drawer_actions.count():
            item = self._drawer_actions.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for text, slot in (("Rename", self._rename_selected), ("Restart", self._restart_selected), ("Forget Device", self._forget_selected)):
            btn = QPushButton(text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(34)
            btn.clicked.connect(slot)
            btn.setStyleSheet(_soft_button_style())
            self._drawer_actions.addWidget(btn)
        self._animate_drawer(True)

    def _close_drawer(self):
        self._animate_drawer(False)

    def _rename_selected(self):
        if not self._selected_device_id:
            return
        device = self._service.get_device(self._selected_device_id)
        if not device:
            return
        from PyQt6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(self, "Rename Device", "New name:", text=str(device.get("name", "")))
        if ok and new_name.strip():
            self._service.rename_device(self._selected_device_id, new_name.strip())
            self._refresh()

    def _restart_selected(self):
        if self._selected_device_id:
            self._service.restart_device(self._selected_device_id)
            self._refresh()

    def _forget_selected(self):
        if self._selected_device_id:
            self._service.forget_device(self._selected_device_id)
            self._selected_device_id = None
            self._close_drawer()
            self._refresh()

    def _refresh(self):
        devices = self._service.list_devices()
        self._refresh_devices(devices)
        self._status_chip.setText("  Home Connected\n  Online" if devices else "  Home Connected\n  Ready")
        self._empty_state.setVisible(not devices)
        self._device_scroll.setVisible(bool(devices))

    def _refresh_devices(self, devices: list[dict[str, Any]]):
        while self._device_grid.count():
            item = self._device_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._device_tiles.clear()
        if not devices:
            return
        columns = self._device_columns()
        self._device_columns_cached = columns
        for idx, device in enumerate(devices):
            tile = _DeviceTile(device)
            tile.select_requested.connect(self._on_tile_selected)
            tile.action_requested.connect(self._on_device_action)
            tile.set_active(str(device.get("id")) == self._selected_device_id)
            self._device_grid.addWidget(tile, idx // columns, idx % columns)
            self._device_tiles.append(tile)

    def _refresh_activity(self):
        while self._activity_list.count():
            item = self._activity_list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._activity_items = self._service.recent_activity(10)
        if not self._activity_items:
            empty = QLabel("No recent activity yet.")
            empty.setStyleSheet(f"color: {TEXT_DIM};")
            self._activity_list.addWidget(empty)
            return
        for row in self._activity_items:
            item = QFrame()
            item.setStyleSheet("QFrame { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; }")
            box = QHBoxLayout(item)
            box.setContentsMargins(10, 8, 10, 8)
            box.setSpacing(8)
            time_lbl = QLabel(QDateTime.fromMSecsSinceEpoch(int(row["created_at"])).toString("h:mm AP"))
            time_lbl.setStyleSheet(f"color: {TEXT_DIM};")
            box.addWidget(time_lbl)
            text_box = QVBoxLayout()
            title = QLabel(str(row["title"]))
            title.setStyleSheet(f"color: {TEXT}; font-weight: 700;")
            detail = QLabel(str(row["detail"]))
            detail.setWordWrap(True)
            detail.setStyleSheet(f"color: {TEXT_DIM};")
            text_box.addWidget(title)
            text_box.addWidget(detail)
            box.addLayout(text_box, 1)
            self._activity_list.addWidget(item)

    def _on_tile_selected(self, device_id: str):
        device = self._service.get_device(device_id)
        if not device:
            return
        self._selected_device_id = device_id
        for tile in self._device_tiles:
            tile.set_active(str(tile.device.get("id")) == device_id)
        self._open_drawer(device)

    def _on_device_action(self, device_id: str, action: str, payload: dict):
        try:
            self._service.execute_device_action(device_id, action, payload)
        except Exception:
            return
        self._refresh()
        device = self._service.get_device(device_id)
        if device:
            self._open_drawer(device)

    def _toggle_voice_mode(self):
        states = ["Idle", "Listening", "Thinking", "Executing", "Completed"]
        self._voice_phase = (self._voice_phase + 1) % len(states)
        self._voice_state = states[self._voice_phase]
        # Some UI paths may call this before voice widgets are built; guard access.
        if hasattr(self, "_voice_state_lbl") and isinstance(getattr(self, "_voice_state_lbl"), QLabel):
            try:
                self._voice_state_lbl.setText(f"{self._voice_state}...")
            except Exception:
                pass
        if hasattr(self, "_voice_state_small") and isinstance(getattr(self, "_voice_state_small"), QLabel):
            try:
                self._voice_state_small.setText(self._voice_state)
            except Exception:
                pass

    def _animate_voice(self):
        self._voice_phase += 1
        for idx, bar in enumerate(self._wave_bars):
            height = 8 + int(18 * abs(((self._voice_phase + idx) % 14) - 7) / 7)
            bar.setFixedHeight(max(8, min(40, height)))
            bar.setStyleSheet(f"background: {'rgba(255,69,69,0.55)' if self._voice_state in ('Listening', 'Executing') else 'rgba(255,255,255,0.18)'}; border-radius: 2px;")
        for idx, bar in enumerate(self._voice_small_bars):
            height = 6 + int(10 * abs(((self._voice_phase + idx) % 10) - 5) / 5)
            bar.setFixedHeight(max(6, min(24, height)))
            bar.setStyleSheet(f"background: {'rgba(255,69,69,0.35)' if self._voice_state in ('Listening', 'Executing') else 'rgba(255,255,255,0.15)'}; border-radius: 2px;")
        self._voice_cmd_lbl.setText({"Idle": '"Brahma"', "Listening": '"Turn bedroom fan to speed 4"', "Thinking": '"Understanding..."', "Executing": '"Applying command..."', "Completed": '"Done"'}.get(self._voice_state, '"Brahma"'))
        self._mic_orb.setText("🎤" if self._voice_state in ("Listening", "Executing") else "◉")

    def _open_add_device(self):
        dialog = AddDeviceDialog(self._service, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        payload = dialog.result_payload()
        provider_key = str(payload.get("provider_key", ""))
        selected = list(payload.get("selected_external_ids", []))
        if not provider_key or not selected:
            return
        creds = dict(payload.get("credentials", {}))
        label = str(payload.get("account_label", "Home"))
        try:
            self._service.connect_devices(provider_key, label, creds, selected)
        except Exception:
            return
        self._refresh()
