from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Iterable

from PyQt6.QtCore import QEasingCurve, QDateTime, QPropertyAnimation, QRect, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from smart_home import SmartHomeService


BG = "#050608"
PANEL = "#0a0b0f"
PANEL_2 = "#0f1015"
BORDER = "rgba(255,69,69,80)"
BORDER_HI = "rgba(255,69,69,165)"
TEXT = "#FFFFFF"
TEXT_DIM = "rgba(255,255,255,0.66)"
TEXT_MED = "rgba(255,255,255,0.82)"
ACCENT = "#ff4545"
ACCENT_SOFT = "rgba(255,69,69,0.12)"
ACCENT_FAINT = "rgba(255,69,69,0.04)"
GOOD = "#35ff75"
WARN = "#ffd166"
BLUE = "#4fc3ff"


@dataclass(frozen=True)
class DeviceSpec:
    name: str
    manufacturer: str
    room: str
    status: str
    battery: str
    signal: int
    power: bool
    kind: str
    detail_a: str
    detail_b: str
    detail_c: str
    firmware: str
    mac: str
    ip: str
    power_usage: str


class ClickableCard(QFrame):
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


class MetricCard(QFrame):
    def __init__(self, label: str, value: str, detail: str = "", level: int = 0, parent=None):
        super().__init__(parent)
        self.setObjectName("MetricCard")
        self.setStyleSheet(
            f"""
            QFrame#MetricCard {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(15,15,15,245),
                    stop:1 rgba(8,8,8,235));
                border: 1px solid {BORDER};
                border-radius: 14px;
            }}
            """
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)
        lbl = QLabel(label.upper())
        lbl.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        lbl.setStyleSheet("color: rgba(255,255,255,0.56); background: transparent; letter-spacing: 1px;")
        lay.addWidget(lbl)
        self._value_lbl = QLabel(value)
        self._value_lbl.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
        self._value_lbl.setStyleSheet(f"color: {TEXT}; background: transparent;")
        lay.addWidget(self._value_lbl)
        self._detail_lbl = QLabel(detail)
        self._detail_lbl.setFont(QFont("Segoe UI", 8))
        self._detail_lbl.setStyleSheet(f"color: {TEXT_DIM}; background: transparent;")
        lay.addWidget(self._detail_lbl)
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(5)
        self._bar.setStyleSheet(
            f"""
            QProgressBar {{
                background: rgba(255,255,255,0.05);
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background: {ACCENT};
                border-radius: 2px;
            }}
            """
        )
        self._bar.setValue(level)
        lay.addWidget(self._bar)

    def set_value(self, value: str, detail: str = "", level: int | None = None):
        self._value_lbl.setText(value)
        if detail:
            self._detail_lbl.setText(detail)
        if level is not None:
            self._bar.setValue(max(0, min(100, int(level))))


class DeviceCard(ClickableCard):
    toggled = pyqtSignal(bool)
    selected = pyqtSignal()

    def __init__(self, spec: DeviceSpec, parent=None):
        super().__init__(parent)
        self.spec = spec
        self._power_on = bool(spec.power)
        self._selected = False
        self.setObjectName("DeviceCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(178)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(self._style(False))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(10)
        icon = QLabel(spec.name[:1].upper())
        icon.setFixedSize(34, 34)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        icon.setStyleSheet(
            f"color: {TEXT}; background: {ACCENT_FAINT}; border: 1px solid {BORDER_HI}; border-radius: 17px;"
        )
        head.addWidget(icon)

        meta = QVBoxLayout()
        meta.setSpacing(1)
        name = QLabel(spec.name)
        name.setWordWrap(True)
        name.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        name.setStyleSheet(f"color: {TEXT}; background: transparent;")
        sub = QLabel(f"{spec.manufacturer} • {spec.room}")
        sub.setFont(QFont("Segoe UI", 8))
        sub.setStyleSheet(f"color: {TEXT_DIM}; background: transparent;")
        meta.addWidget(name)
        meta.addWidget(sub)
        head.addLayout(meta, 1)

        self._status_chip = QLabel(spec.status.upper())
        self._status_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_chip.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        self._status_chip.setStyleSheet(
            f"color: {GOOD}; background: rgba(53,255,117,0.08); border: 1px solid rgba(53,255,117,0.22); border-radius: 10px; padding: 4px 8px;"
        )
        head.addWidget(self._status_chip)
        lay.addLayout(head)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        self._battery_lbl = self._kv(grid, 0, 0, "Battery", spec.battery)
        self._signal_lbl = self._kv(grid, 0, 1, "Signal", f"{spec.signal}%")
        self._room_lbl = self._kv(grid, 1, 0, "Room", spec.room)
        self._usage_lbl = self._kv(grid, 1, 1, "Power", spec.power_usage)
        lay.addLayout(grid)

        self._details = QLabel(f"Speed / Brightness / Mode: {spec.detail_a} • {spec.detail_b} • {spec.detail_c}")
        self._details.setWordWrap(True)
        self._details.setFont(QFont("Segoe UI", 8))
        self._details.setStyleSheet(f"color: {TEXT_DIM}; background: transparent;")
        lay.addWidget(self._details)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self._power_btn = QPushButton("ON" if self._power_on else "OFF")
        self._power_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._power_btn.setFixedHeight(30)
        self._power_btn.setStyleSheet(self._btn_style(selected=False))
        self._power_btn.clicked.connect(self._toggle_power)
        action_row.addWidget(self._power_btn)

        self._settings_btn = QPushButton("Settings")
        self._settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_btn.setFixedHeight(30)
        self._settings_btn.setStyleSheet(self._btn_style(selected=False, secondary=True))
        action_row.addWidget(self._settings_btn)
        lay.addLayout(action_row)

    def _kv(self, grid: QGridLayout, row: int, col: int, key: str, value: str) -> QLabel:
        box = QVBoxLayout()
        wrap = QFrame()
        wrap.setStyleSheet("background: transparent;")
        wrap_lay = QVBoxLayout(wrap)
        wrap_lay.setContentsMargins(0, 0, 0, 0)
        wrap_lay.setSpacing(0)
        k = QLabel(key.upper())
        k.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        k.setStyleSheet("color: rgba(255,255,255,0.48); background: transparent;")
        v = QLabel(value)
        v.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        v.setStyleSheet("color: #FFFFFF; background: transparent;")
        wrap_lay.addWidget(k)
        wrap_lay.addWidget(v)
        grid.addWidget(wrap, row, col)
        return v

    def _btn_style(self, selected: bool, secondary: bool = False) -> str:
        if selected:
            return f"""
                QPushButton {{
                    background: {ACCENT_SOFT};
                    color: {TEXT};
                    border: 1px solid {BORDER_HI};
                    border-radius: 9px;
                }}
            """
        if secondary:
            return f"""
                QPushButton {{
                    background: rgba(255,255,255,0.03);
                    color: {TEXT};
                    border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 9px;
                }}
                QPushButton:hover {{
                    border: 1px solid {BORDER_HI};
                    background: rgba(255,69,69,0.06);
                }}
            """
        return f"""
            QPushButton {{
                background: rgba(255,69,69,0.12);
                color: {TEXT};
                border: 1px solid {BORDER_HI};
                border-radius: 9px;
            }}
            QPushButton:hover {{
                background: rgba(255,69,69,0.18);
            }}
        """

    def _style(self, active: bool) -> str:
        return f"""
            QFrame#DeviceCard {{
                background: {'qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(18,18,20,245), stop:1 rgba(8,8,10,235))' if active else 'qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(14,14,17,240), stop:1 rgba(7,7,9,235))'};
                border: 1px solid {'rgba(255,69,69,190)' if active else BORDER};
                border-radius: 14px;
            }}
        """

    def set_selected(self, active: bool):
        self._selected = bool(active)
        self.setStyleSheet(self._style(self._selected))

    def _toggle_power(self):
        self._power_on = not self._power_on
        self._power_btn.setText("ON" if self._power_on else "OFF")
        self._power_btn.setStyleSheet(self._btn_style(selected=self._power_on))
        self.toggled.emit(self._power_on)
        self.selected.emit()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit()


class RoomTile(ClickableCard):
    def __init__(self, room: str, description: str, count: int, parent=None):
        super().__init__(parent)
        self.room = room
        self._selected = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(110)
        self.setStyleSheet(self._style(False))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)
        top = QHBoxLayout()
        title = QLabel(room)
        title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {TEXT}; background: transparent;")
        badge = QLabel(f"{count} DEVICES")
        badge.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        badge.setStyleSheet(
            "color: rgba(255,255,255,0.58); background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 3px 8px;"
        )
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(badge)
        lay.addLayout(top)
        sub = QLabel(description)
        sub.setWordWrap(True)
        sub.setFont(QFont("Segoe UI", 8))
        sub.setStyleSheet(f"color: {TEXT_DIM}; background: transparent;")
        lay.addWidget(sub)
        self._chips = QLabel("Fan • Light • Power")
        self._chips.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self._chips.setStyleSheet("color: rgba(255,255,255,0.75); background: transparent;")
        lay.addWidget(self._chips)

    def _style(self, selected: bool) -> str:
        return f"""
            QFrame {{
                background: {'rgba(255,69,69,0.10)' if selected else 'qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(13,13,16,245), stop:1 rgba(8,8,10,235))'};
                border: 1px solid {'rgba(255,69,69,190)' if selected else BORDER};
                border-radius: 14px;
            }}
        """

    def set_selected(self, active: bool):
        self._selected = bool(active)
        self.setStyleSheet(self._style(self._selected))


class BrahmaHomePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("BrahmaHomePage")
        self.setStyleSheet(f"QWidget#BrahmaHomePage {{ background: {BG}; }}")

        self._selected_room = "All"
        self._selected_device_id = ""
        self._voice_state = "Listening"
        self._scan_active = False
        self._scan_phase = 0
        self._history_items: list[str] = []

        self._devices: list[DeviceSpec] = [
            DeviceSpec("Atomberg Renesa Fan", "Atomberg", "Bedroom", "Connected", "100%", 94, True, "fan", "Speed 1 / 2 / 3 / 4 / 5", "Sleep Mode", "Timer", "v2.4.1", "A1:B2:C3:D4:E5:F1", "192.168.0.24", "18W"),
            DeviceSpec("Philips Hue Light", "Philips", "Living Room", "Connected", "100%", 88, True, "light", "Warm White / 70%", "Color Scene", "Dimmer", "v4.5.0", "A1:B2:C3:D4:E5:F2", "192.168.0.25", "7W"),
            DeviceSpec("TP-Link Kasa Plug", "TP-Link", "Office", "Connected", "100%", 90, True, "plug", "Power ON / OFF", "Energy View", "Schedule", "v3.1.9", "A1:B2:C3:D4:E5:F3", "192.168.0.26", "2W"),
            DeviceSpec("LG Smart TV", "LG", "Living Room", "Connected", "100%", 82, False, "tv", "HDMI 1 / Volume 32", "Cinema Mode", "Power Save", "v9.8.1", "A1:B2:C3:D4:E5:F4", "192.168.0.27", "96W"),
            DeviceSpec("Smart AC", "Daikin", "Bedroom", "Connected", "100%", 86, True, "ac", "24°C / Cooling", "Fan Speed Auto", "Turbo Mode", "v6.2.0", "A1:B2:C3:D4:E5:F5", "192.168.0.28", "430W"),
            DeviceSpec("Robot Vacuum", "Roborock", "Bathroom", "Docked", "78%", 78, False, "vacuum", "Cleaning Schedule", "Docked", "Mapping", "v5.0.7", "A1:B2:C3:D4:E5:F6", "192.168.0.29", "25W"),
            DeviceSpec("Smart Curtain", "Somfy", "Balcony", "Connected", "92%", 80, False, "curtain", "Open 30%", "Scene Sync", "Sunset", "v1.7.3", "A1:B2:C3:D4:E5:F7", "192.168.0.30", "1W"),
            DeviceSpec("Matter Door Sensor", "Matter", "Kitchen", "Connected", "66%", 75, True, "sensor", "Door Open/Close", "Automation", "Presence", "v1.2.4", "A1:B2:C3:D4:E5:F8", "192.168.0.31", "0W"),
        ]
        self._room_tiles: list[RoomTile] = []
        self._device_cards: list[DeviceCard] = []
        self._platform_cards: list[QFrame] = []
        self._discovery_rows: list[QFrame] = []
        self._room_chips: list[QPushButton] = []
        self._voice_bars: list[QFrame] = []

        self._build_ui()

        self._tick = QTimer(self)
        self._tick.timeout.connect(self._on_tick)
        self._tick.start(550)
        self._on_tick()
        self._select_device(self._devices[0].name)
        self._set_room("All")

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(12)

        header = QFrame()
        header.setStyleSheet(
            f"QFrame {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(12,12,14,245), stop:1 rgba(8,8,10,235)); border: 1px solid {BORDER}; border-radius: 16px; }}"
        )
        h = QHBoxLayout(header)
        h.setContentsMargins(16, 14, 16, 14)
        h.setSpacing(12)
        title_box = QVBoxLayout()
        title = QLabel("BRAHMA HOME")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Black))
        title.setStyleSheet(f"color: {TEXT}; background: transparent; letter-spacing: 2px;")
        subtitle = QLabel("Control your smart devices using AI.")
        subtitle.setFont(QFont("Segoe UI", 9))
        subtitle.setStyleSheet(f"color: {TEXT_DIM}; background: transparent;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        h.addLayout(title_box, 1)
        self._status_chip = self._chip("Home Status", "ONLINE")
        self._time_chip = self._chip("Current Time", "00:00")
        self._weather_chip = self._chip("Weather", "Clear")
        self._temp_chip = self._chip("Temperature", "29°C")
        for chip in (self._status_chip, self._time_chip, self._weather_chip, self._temp_chip):
            h.addWidget(chip)
        root.addWidget(header)

        stats = QHBoxLayout()
        stats.setSpacing(10)
        self._metric_devices = MetricCard("Connected Devices", "18", "16 online", 89)
        self._metric_rooms = MetricCard("Rooms", "6", "Bedroom • Living Room • Kitchen", 72)
        self._metric_voice = MetricCard("Voice Assistant", "Listening", "Wake word enabled", 58)
        self._metric_energy = MetricCard("Energy", "2.9 kWh", "Today usage", 64)
        for card in (self._metric_devices, self._metric_rooms, self._metric_voice, self._metric_energy):
            stats.addWidget(card)
        root.addLayout(stats)

        main = QHBoxLayout()
        main.setSpacing(12)
        root.addLayout(main, 1)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        left_content = QWidget()
        left_content.setStyleSheet("background: transparent;")
        self._left_lay = QVBoxLayout(left_content)
        self._left_lay.setContentsMargins(0, 0, 0, 0)
        self._left_lay.setSpacing(12)
        left_scroll.setWidget(left_content)
        main.addWidget(left_scroll, 1)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        right_scroll.setMinimumWidth(360)
        right_scroll.setMaximumWidth(420)
        right_content = QWidget()
        right_content.setStyleSheet("background: transparent;")
        self._right_lay = QVBoxLayout(right_content)
        self._right_lay.setContentsMargins(0, 0, 0, 0)
        self._right_lay.setSpacing(12)
        right_scroll.setWidget(right_content)
        main.addWidget(right_scroll, 0)

        self._build_left_sections()
        self._build_right_sections()

    def _chip(self, label: str, value: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; }"
        )
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(2)
        k = QLabel(label.upper())
        k.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        k.setStyleSheet("color: rgba(255,255,255,0.52); background: transparent; letter-spacing: 1px;")
        v = QLabel(value)
        v.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        v.setStyleSheet("color: #FFFFFF; background: transparent;")
        lay.addWidget(k)
        lay.addWidget(v)
        frame._value_lbl = v  # type: ignore[attr-defined]
        return frame

    def _section_frame(self, title: str, subtitle: str = "") -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(13,13,16,245), stop:1 rgba(8,8,10,235)); border: 1px solid {BORDER}; border-radius: 16px; }}"
        )
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)
        if title:
            head = QHBoxLayout()
            head.setSpacing(8)
            title_lbl = QLabel(title.upper())
            title_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            title_lbl.setStyleSheet(f"color: {TEXT}; background: transparent; letter-spacing: 1px;")
            head.addWidget(title_lbl)
            if subtitle:
                sub = QLabel(subtitle)
                sub.setFont(QFont("Segoe UI", 8))
                sub.setStyleSheet(f"color: {TEXT_DIM}; background: transparent;")
                head.addWidget(sub)
            head.addStretch(1)
            lay.addLayout(head)
            line = QFrame()
            line.setFixedHeight(1)
            line.setStyleSheet("background: rgba(255,69,69,0.22);")
            lay.addWidget(line)
        return frame, lay

    def _build_left_sections(self):
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search devices by room, manufacturer, or name...")
        self._search.setFixedHeight(38)
        self._search.setFont(QFont("Segoe UI", 10))
        self._search.textChanged.connect(self._apply_filters)
        self._search.setStyleSheet(
            "QLineEdit { background: rgba(9,10,13,245); color: #FFFFFF; border: 1px solid rgba(255,69,69,100); border-radius: 12px; padding: 0 12px; }"
        )
        filter_row.addWidget(self._search, 1)
        scan_btn = QPushButton("Scan For Devices")
        scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        scan_btn.setFixedHeight(38)
        scan_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        scan_btn.setStyleSheet(self._soft_button_style())
        scan_btn.clicked.connect(self._toggle_scan)
        filter_row.addWidget(scan_btn)
        self._left_lay.addLayout(filter_row)

        room_row = QHBoxLayout()
        room_row.setSpacing(8)
        for room in ("All", "Bedroom", "Living Room", "Kitchen", "Office", "Bathroom", "Balcony"):
            btn = QPushButton(room)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(32)
            btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            btn.setStyleSheet(self._room_chip_style(False))
            btn.clicked.connect(partial(self._set_room, room))
            self._room_chips.append(btn)
            room_row.addWidget(btn)
        room_row.addStretch(1)
        self._left_lay.addLayout(room_row)

        map_frame, map_lay = self._section_frame("Home Map", "Interactive floor plan")
        self._left_lay.addWidget(map_frame)
        map_grid = QGridLayout()
        map_grid.setHorizontalSpacing(10)
        map_grid.setVerticalSpacing(10)
        rooms = [
            ("Bedroom", "Fan • Light • AC", 4),
            ("Living Room", "TV • Light • Plug", 3),
            ("Kitchen", "Sensor • Light • Plug", 3),
            ("Office", "Plug • Light • Speaker", 2),
            ("Bathroom", "Vacuum • Sensor", 2),
            ("Balcony", "Curtain • Light", 2),
        ]
        for idx, (name, desc, count) in enumerate(rooms):
            tile = RoomTile(name, desc, count)
            tile.clicked.connect(partial(self._set_room, name))
            self._room_tiles.append(tile)
            map_grid.addWidget(tile, idx // 3, idx % 3)
        map_lay.addLayout(map_grid)

        devices_frame, devices_lay = self._section_frame("Device Grid", "Click any device for controls")
        self._left_lay.addWidget(devices_frame)
        self._device_grid = QGridLayout()
        self._device_grid.setHorizontalSpacing(10)
        self._device_grid.setVerticalSpacing(10)
        devices_lay.addLayout(self._device_grid)
        for spec in self._devices:
            card = DeviceCard(spec)
            card.clicked.connect(partial(self._select_device, spec.name))
            card.toggled.connect(partial(self._on_device_toggled, spec))
            self._device_cards.append(card)
        self._rebuild_device_grid()

        quick_frame, quick_lay = self._section_frame("Quick Actions", "One click automations")
        self._left_lay.addWidget(quick_frame)
        quick_grid = QGridLayout()
        quick_grid.setHorizontalSpacing(10)
        quick_grid.setVerticalSpacing(10)
        self._quick_actions = [
            ("Good Night", "Turn lights off, lower AC, lock doors", "Night"),
            ("Good Morning", "Open curtains, set fan speed 2", "Morning"),
            ("Movie Mode", "Dim lights, close curtains, TV on", "Movie"),
            ("Away Mode", "Power down everything", "Away"),
            ("Party Mode", "Color lights and music", "Party"),
            ("Sleep Mode", "Quiet house, low lights", "Sleep"),
            ("Turn Everything Off", "Hard shut down all devices", "Power"),
            ("Turn On All Lights", "Bright home lighting", "Lights"),
        ]
        for idx, (label, desc, tag) in enumerate(self._quick_actions):
            btn = QPushButton(f"{label}\n{desc}")
            btn.setMinimumHeight(74)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            btn.setStyleSheet(
                """
                QPushButton {
                    text-align: left;
                    white-space: normal;
                    background: rgba(255,255,255,0.03);
                    color: #FFFFFF;
                    border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 12px;
                    padding: 10px 12px;
                }
                QPushButton:hover {
                    background: rgba(255,69,69,0.08);
                    border: 1px solid rgba(255,69,69,0.34);
                }
                """
            )
            btn.clicked.connect(partial(self._run_quick_action, label, tag))
            quick_grid.addWidget(btn, idx // 2, idx % 2)
        quick_lay.addLayout(quick_grid)

        rooms_frame, rooms_lay = self._section_frame("Rooms", "Selecting one filters the dashboard")
        self._left_lay.addWidget(rooms_frame)
        rooms_grid = QGridLayout()
        rooms_grid.setHorizontalSpacing(10)
        rooms_grid.setVerticalSpacing(10)
        for idx, room in enumerate(("Bedroom", "Living Room", "Kitchen", "Office", "Bathroom", "Balcony")):
            tile = QPushButton(room)
            tile.setCheckable(True)
            tile.setCursor(Qt.CursorShape.PointingHandCursor)
            tile.setMinimumHeight(46)
            tile.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            tile.setStyleSheet(self._room_card_style(False))
            tile.clicked.connect(partial(self._set_room, room))
            rooms_grid.addWidget(tile, idx // 3, idx % 3)
            self._room_chips.append(tile)
        rooms_lay.addLayout(rooms_grid)

        scenes_frame, scenes_lay = self._section_frame("Scenes", "One click executes every action")
        self._left_lay.addWidget(scenes_frame)
        scenes_grid = QGridLayout()
        scenes_grid.setHorizontalSpacing(10)
        scenes_grid.setVerticalSpacing(10)
        for idx, (name, desc) in enumerate([
            ("Movie Mode", "Dim lights + TV"),
            ("Gaming Mode", "Ambient lights + AC"),
            ("Study Mode", "Cool light + focus"),
            ("Dinner Mode", "Warm lights"),
            ("Sleep Mode", "Curtains + quiet"),
            ("Vacation Mode", "Everything off"),
        ]):
            btn = QPushButton(f"{name}\n{desc}")
            btn.setMinimumHeight(70)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            btn.setStyleSheet(self._scene_style())
            btn.clicked.connect(partial(self._run_quick_action, name, name))
            scenes_grid.addWidget(btn, idx // 2, idx % 2)
        scenes_lay.addLayout(scenes_grid)

        automation_frame, automation_lay = self._section_frame("Automations", "Editable workflow builder")
        self._left_lay.addWidget(automation_frame)
        auto_steps = [
            "Good Night",
            "Turn Lights Off",
            "Set Atomberg Fan Speed 2",
            "TV Off",
            "Lock Door",
            "AC 25°",
        ]
        for step in auto_steps:
            row = QLabel(f"↓ {step}")
            row.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold if step == "Good Night" else QFont.Weight.Normal))
            row.setStyleSheet(f"color: {TEXT}; background: transparent; padding: 6px 8px;")
            automation_lay.addWidget(row)
        auto_btn_row = QHBoxLayout()
        for text in ("Enable", "Disable", "Run Now", "Delete"):
            btn = QPushButton(text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(34)
            btn.setStyleSheet(self._soft_button_style())
            btn.clicked.connect(partial(self._record_history, f"Automation action: {text}"))
            auto_btn_row.addWidget(btn)
        automation_lay.addLayout(auto_btn_row)

        energy_frame, energy_lay = self._section_frame("Energy Monitor", "Today's and live power usage")
        self._left_lay.addWidget(energy_frame)
        self._energy_bars = []
        for label, value in (("Today's Consumption", 54), ("Weekly", 67), ("Monthly", 73), ("Top Devices", 49)):
            row = QHBoxLayout()
            txt = QLabel(label)
            txt.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            txt.setStyleSheet(f"color: {TEXT}; background: transparent;")
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(value)
            bar.setTextVisible(False)
            bar.setFixedHeight(8)
            bar.setStyleSheet(
                f"QProgressBar {{ background: rgba(255,255,255,0.05); border: none; border-radius: 4px; }} QProgressBar::chunk {{ background: {ACCENT}; border-radius: 4px; }}"
            )
            self._energy_bars.append(bar)
            row.addWidget(txt, 0)
            row.addWidget(bar, 1)
            energy_lay.addLayout(row)

        discovery_frame, discovery_lay = self._section_frame("Device Discovery", "Scan for new devices")
        self._left_lay.addWidget(discovery_frame)
        self._scan_status_lbl = QLabel("Idle")
        self._scan_status_lbl.setStyleSheet(f"color: {TEXT_DIM}; background: transparent;")
        discovery_lay.addWidget(self._scan_status_lbl)
        self._discovery_scroll = QVBoxLayout()
        discovery_lay.addLayout(self._discovery_scroll)
        self._build_discovery_rows()

        platforms_frame, platforms_lay = self._section_frame("Supported Platforms", "Provider-backed architecture")
        self._left_lay.addWidget(platforms_frame)
        platform_grid = QGridLayout()
        platform_grid.setHorizontalSpacing(10)
        platform_grid.setVerticalSpacing(10)
        for idx, (name, status, action) in enumerate([
            ("Atomberg Home", "Connected", "Manage"),
            ("TP-Link Kasa", "Connected", "Manage"),
            ("Matter", "Connected", "Manage"),
            ("Home Assistant", "Connected", "Manage"),
            ("Smart Life (Tuya)", "Available", "Connect"),
            ("Philips Hue", "Available", "Connect"),
            ("Google Home", "Coming Soon", "Coming Soon"),
            ("Apple HomeKit", "Coming Soon", "Coming Soon"),
            ("Samsung SmartThings", "Coming Soon", "Coming Soon"),
            ("LG ThinQ", "Coming Soon", "Coming Soon"),
            ("ESPHome", "Coming Soon", "Coming Soon"),
            ("MQTT", "Coming Soon", "Coming Soon"),
        ]):
            card = self._platform_card(name, status, action)
            self._platform_cards.append(card)
            platform_grid.addWidget(card, idx // 2, idx % 2)
        platforms_lay.addLayout(platform_grid)

        history_frame, history_lay = self._section_frame("History", "Every device action is logged")
        self._left_lay.addWidget(history_frame)
        self._history_lay = QVBoxLayout()
        self._history_lay.setSpacing(8)
        history_lay.addLayout(self._history_lay)
        self._history_lay.addWidget(self._history_entry("9:15 PM", "Bedroom Fan → Speed 3"))
        self._history_lay.addWidget(self._history_entry("9:18 PM", "Movie Mode Activated"))
        self._history_lay.addWidget(self._history_entry("9:45 PM", "TV Turned Off"))
        self._history_lay.addStretch(1)
        self._left_lay.addStretch(1)

    def _build_right_sections(self):
        details_frame, details_lay = self._section_frame("Device Details", "Click any device")
        self._right_lay.addWidget(details_frame)
        self._detail_name = QLabel("Select a device")
        self._detail_name.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._detail_name.setStyleSheet(f"color: {TEXT}; background: transparent;")
        details_lay.addWidget(self._detail_name)
        self._detail_meta = QLabel("")
        self._detail_meta.setWordWrap(True)
        self._detail_meta.setStyleSheet(f"color: {TEXT_DIM}; background: transparent;")
        details_lay.addWidget(self._detail_meta)
        self._detail_info = QLabel("")
        self._detail_info.setWordWrap(True)
        self._detail_info.setStyleSheet(f"color: {TEXT_MED}; background: transparent;")
        details_lay.addWidget(self._detail_info)
        detail_btn_row = QHBoxLayout()
        for text in ("Rename", "Forget Device", "Restart Device"):
            btn = QPushButton(text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(34)
            btn.setStyleSheet(self._soft_button_style())
            btn.clicked.connect(partial(self._record_history, f"Device detail action: {text}"))
            detail_btn_row.addWidget(btn)
        details_lay.addLayout(detail_btn_row)

        voice_frame, voice_lay = self._section_frame("Brahma Voice", "Wake word + commands")
        self._right_lay.addWidget(voice_frame)
        self._voice_state_lbl = QLabel("Listening")
        self._voice_state_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self._voice_state_lbl.setStyleSheet(f"color: {ACCENT}; background: transparent;")
        voice_lay.addWidget(self._voice_state_lbl)
        self._voice_wave = QHBoxLayout()
        self._voice_wave.setSpacing(4)
        for _ in range(12):
            bar = QFrame()
            bar.setFixedSize(8, 20)
            bar.setStyleSheet("background: rgba(255,255,255,0.10); border-radius: 3px;")
            self._voice_wave.addWidget(bar)
            self._voice_bars.append(bar)
        voice_lay.addLayout(self._voice_wave)
        self._last_command_lbl = QLabel('Last Command: "Brahma, turn bedroom fan to speed 5."')
        self._last_command_lbl.setWordWrap(True)
        self._last_command_lbl.setStyleSheet(f"color: {TEXT_MED}; background: transparent;")
        voice_lay.addWidget(self._last_command_lbl)
        self._last_result_lbl = QLabel("Result: Bedroom fan set to speed 5.")
        self._last_result_lbl.setWordWrap(True)
        self._last_result_lbl.setStyleSheet(f"color: {TEXT_MED}; background: transparent;")
        voice_lay.addWidget(self._last_result_lbl)
        voice_btn_row = QHBoxLayout()
        self._mic_btn = QPushButton("Mic")
        self._mic_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mic_btn.setMinimumHeight(34)
        self._mic_btn.setStyleSheet(self._soft_button_style())
        self._mic_btn.clicked.connect(self._toggle_voice)
        voice_btn_row.addWidget(self._mic_btn)
        for text in ("Idle", "Listening", "Thinking", "Executing"):
            btn = QPushButton(text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(34)
            btn.setStyleSheet(self._soft_button_style())
            btn.clicked.connect(partial(self._set_voice_state, text))
            voice_btn_row.addWidget(btn)
        voice_lay.addLayout(voice_btn_row)

        convo_frame, convo_lay = self._section_frame("Smart Conversation", "Understanding → Planning → Executing → Completed")
        self._right_lay.addWidget(convo_frame)
        self._convo_status = QLabel("Completed")
        self._convo_status.setStyleSheet(f"color: {GOOD}; background: transparent; font-weight: 700;")
        convo_lay.addWidget(self._convo_status)
        for stage in ("Understanding...", "Planning...", "Executing...", "Completed."):
            lbl = QLabel(stage)
            lbl.setStyleSheet(f"color: {TEXT_MED}; background: transparent;")
            convo_lay.addWidget(lbl)
        self._convo_hint = QLabel("Brahma is ready for the next command.")
        self._convo_hint.setStyleSheet(f"color: {TEXT_DIM}; background: transparent;")
        convo_lay.addWidget(self._convo_hint)

        notif_frame, notif_lay = self._section_frame("Notifications", "Smart alerts")
        self._right_lay.addWidget(notif_frame)
        for text in (
            "Front Door Open",
            "Water Leak Detected",
            "Device Offline",
            "Low Battery",
            "Firmware Available",
        ):
            notif_lay.addWidget(self._mini_row("!", text, "Alert"))

        rec_frame, rec_lay = self._section_frame("AI Recommendations", "Proactive suggestions")
        self._right_lay.addWidget(rec_frame)
        for text in (
            "Your bedroom fan has been running for 7 hours.",
            "Would you like me to turn it off?",
            "You usually activate Movie Mode at 8 PM.",
            "Create automation?",
        ):
            rec_lay.addWidget(self._recommendation_card(text))

        self._right_lay.addStretch(1)

    def _soft_button_style(self) -> str:
        return f"""
            QPushButton {{
                background: rgba(255,255,255,0.04);
                color: {TEXT};
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
            }}
            QPushButton:hover {{
                background: rgba(255,69,69,0.08);
                border: 1px solid rgba(255,69,69,0.32);
            }}
        """

    def _room_chip_style(self, active: bool) -> str:
        if active:
            return f"""
                QPushButton {{
                    background: rgba(255,69,69,0.16);
                    color: {TEXT};
                    border: 1px solid rgba(255,69,69,190);
                    border-radius: 10px;
                }}
            """
        return self._soft_button_style()

    def _room_card_style(self, active: bool) -> str:
        if active:
            return f"""
                QPushButton {{
                    background: rgba(255,69,69,0.14);
                    color: {TEXT};
                    border: 1px solid rgba(255,69,69,190);
                    border-radius: 12px;
                    padding: 10px 12px;
                }}
            """
        return f"""
            QPushButton {{
                background: rgba(255,255,255,0.03);
                color: {TEXT};
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                padding: 10px 12px;
            }}
            QPushButton:hover {{
                border: 1px solid rgba(255,69,69,0.32);
                background: rgba(255,69,69,0.06);
            }}
        """

    def _scene_style(self) -> str:
        return f"""
            QPushButton {{
                text-align: left;
                white-space: normal;
                background: rgba(255,255,255,0.03);
                color: {TEXT};
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                padding: 10px 12px;
            }}
            QPushButton:hover {{
                border: 1px solid rgba(255,69,69,0.34);
                background: rgba(255,69,69,0.06);
            }}
        """

    def _mini_row(self, icon: str, title: str, subtitle: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; }"
        )
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(8)
        badge = QLabel(icon)
        badge.setFixedSize(24, 24)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet("background: rgba(255,69,69,0.10); color: #FFFFFF; border: 1px solid rgba(255,69,69,0.22); border-radius: 12px;")
        lay.addWidget(badge)
        box = QVBoxLayout()
        box.setSpacing(0)
        t = QLabel(title)
        t.setStyleSheet(f"color: {TEXT}; background: transparent; font-weight: 700;")
        s = QLabel(subtitle)
        s.setStyleSheet(f"color: {TEXT_DIM}; background: transparent;")
        box.addWidget(t)
        box.addWidget(s)
        lay.addLayout(box, 1)
        return frame

    def _recommendation_card(self, text: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background: rgba(255,69,69,0.05); border: 1px solid rgba(255,69,69,0.16); border-radius: 12px; }"
        )
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(10, 8, 10, 8)
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color: {TEXT_MED}; background: transparent;")
        lay.addWidget(lbl)
        return frame

    def _history_entry(self, stamp: str, text: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; }"
        )
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(8)
        st = QLabel(stamp)
        st.setStyleSheet("color: rgba(255,255,255,0.45); background: transparent;")
        st.setFont(QFont("Segoe UI", 8))
        lay.addWidget(st)
        txt = QLabel(text)
        txt.setWordWrap(True)
        txt.setStyleSheet(f"color: {TEXT}; background: transparent;")
        lay.addWidget(txt, 1)
        return frame

    def _platform_card(self, name: str, status: str, action: str) -> QFrame:
        frame = QFrame()
        frame.setMinimumHeight(72)
        frame.setStyleSheet(
            "QFrame { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; }"
        )
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)
        badge = QLabel(name[:1].upper())
        badge.setFixedSize(28, 28)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet("background: rgba(255,69,69,0.12); color: #FFFFFF; border: 1px solid rgba(255,69,69,0.22); border-radius: 14px;")
        lay.addWidget(badge)
        box = QVBoxLayout()
        t = QLabel(name)
        t.setStyleSheet(f"color: {TEXT}; background: transparent; font-weight: 700;")
        s = QLabel(status)
        s.setStyleSheet(f"color: {GOOD if status == 'Connected' else WARN if status == 'Available' else TEXT_DIM}; background: transparent;")
        box.addWidget(t)
        box.addWidget(s)
        lay.addLayout(box, 1)
        btn = QPushButton(action)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(30)
        btn.setStyleSheet(self._soft_button_style())
        btn.clicked.connect(partial(self._record_history, f"Platform action: {name} → {action}"))
        lay.addWidget(btn)
        return frame

    def _build_discovery_rows(self):
        while self._discovery_scroll.count():
            item = self._discovery_scroll.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._discovery_rows.clear()
        for name in ("Atomberg Fan", "Kasa Plug", "Philips Hue", "Matter Device"):
            row = QFrame()
            row.setStyleSheet(
                "QFrame { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; }"
            )
            lay = QHBoxLayout(row)
            lay.setContentsMargins(10, 8, 10, 8)
            lay.setSpacing(8)
            title = QLabel(name)
            title.setStyleSheet(f"color: {TEXT}; background: transparent; font-weight: 700;")
            lay.addWidget(title, 1)
            for text in ("Connect", "Ignore"):
                btn = QPushButton(text)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setFixedHeight(30)
                btn.setStyleSheet(self._soft_button_style())
                btn.clicked.connect(partial(self._record_history, f"Discovery action: {name} → {text}"))
                lay.addWidget(btn)
            self._discovery_scroll.addWidget(row)
            self._discovery_rows.append(row)

    def _rebuild_device_grid(self):
        while self._device_grid.count():
            item = self._device_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for idx, card in enumerate(self._device_cards):
            self._device_grid.addWidget(card, idx // 2, idx % 2)
        self._apply_filters()

    def _apply_filters(self):
        text = self._search.text().strip().lower()
        for card, spec in zip(self._device_cards, self._devices):
            ok_room = self._selected_room == "All" or spec.room == self._selected_room
            ok_text = not text or text in spec.name.lower() or text in spec.manufacturer.lower() or text in spec.room.lower()
            card.setVisible(ok_room and ok_text)
            card.set_selected(spec.name == self._selected_device_id)
        self._update_room_tiles()
        self._update_recommendations()

    def _update_room_tiles(self):
        for tile in self._room_tiles:
            tile.set_selected(tile.room == self._selected_room)
        for btn in self._room_chips:
            active = btn.text() == self._selected_room
            btn.setChecked(active)
            btn.setStyleSheet(self._room_chip_style(active) if btn.text() in ("All", "Bedroom", "Living Room", "Kitchen", "Office", "Bathroom", "Balcony") else self._room_card_style(active))

    def _set_room(self, room: str):
        self._selected_room = room
        self._apply_filters()
        self._record_history(f"Room filter set to {room}")

    def _select_device(self, name: str):
        self._selected_device_id = name
        self._apply_filters()
        spec = next((d for d in self._devices if d.name == name), None)
        if not spec:
            return
        self._detail_name.setText(spec.name)
        self._detail_meta.setText(f"Manufacturer: {spec.manufacturer}\nRoom: {spec.room}\nStatus: {spec.status}")
        self._detail_info.setText(
            f"Firmware: {spec.firmware}\nMAC: {spec.mac}\nIP: {spec.ip}\nBattery: {spec.battery}\nSignal Strength: {spec.signal}%\nPower Consumption: {spec.power_usage}"
        )
        self._last_command_lbl.setText(f'Last Command: "Brahma, inspect {spec.name.lower()}."')
        self._last_result_lbl.setText(f"Result: {spec.name} is {spec.status.lower()}.")

    def _on_device_toggled(self, spec: DeviceSpec, power_on: bool):
        state = "ON" if power_on else "OFF"
        self._record_history(f"{spec.name} power turned {state}")
        self._set_voice_state("Executing")
        self._last_command_lbl.setText(f'Last Command: "Brahma, switch {spec.name.lower()} {state.lower()}."')
        self._last_result_lbl.setText(f"Result: {spec.name} turned {state.lower()}.")

    def _toggle_scan(self):
        self._scan_active = not self._scan_active
        self._scan_phase = 0
        if self._scan_active:
            self._scan_status_lbl.setText("Scanning for devices...")
            self._record_history("Device scan started")
            self._build_discovery_rows()
        else:
            self._scan_status_lbl.setText("Idle")
            self._record_history("Device scan stopped")

    def _toggle_voice(self):
        self._set_voice_state("Listening" if self._voice_state != "Listening" else "Idle")
        if self._voice_state == "Listening":
            self._record_history("Wake word listening enabled")
        else:
            self._record_history("Mic muted")

    def _set_voice_state(self, state: str):
        self._voice_state = state
        self._voice_state_lbl.setText(state)
        color = {
            "Idle": TEXT_DIM,
            "Listening": ACCENT,
            "Thinking": BLUE,
            "Executing": WARN,
        }.get(state, TEXT)
        self._voice_state_lbl.setStyleSheet(f"color: {color}; background: transparent;")
        self._metric_voice.set_value(state, "Wake word enabled" if state == "Listening" else "Voice ready", 72 if state == "Listening" else 48)
        self._convo_status.setText("Understanding..." if state == "Thinking" else "Planning..." if state == "Executing" else "Completed")
        self._convo_status.setStyleSheet(f"color: {color}; background: transparent; font-weight: 700;")

    def _run_quick_action(self, label: str, tag: str):
        self._set_voice_state("Thinking")
        self._last_command_lbl.setText(f'Last Command: "{label}"')
        result = {
            "Good Night": "Lights off, fan low, doors locked, AC set to 25°.",
            "Good Morning": "Curtains opened, lights on, fan set to 2.",
            "Movie Mode": "Lights dimmed, curtains closed, TV on.",
            "Away Mode": "Everything powered down and secured.",
            "Party Mode": "Color lights enabled and music prepared.",
            "Sleep Mode": "House switched to quiet low-light mode.",
            "Turn Everything Off": "All devices powered off.",
            "Turn On All Lights": "All lights turned on.",
        }.get(label, f"{label} executed.")
        self._last_result_lbl.setText(f"Result: {result}")
        self._set_voice_state("Executing")
        self._record_history(f"{label} activated ({tag})")

    def _record_history(self, text: str):
        stamp = QDateTime.currentDateTime().toString("h:mm AP")
        line = f"{stamp} • {text}"
        self._history_items.insert(0, line)
        self._history_items = self._history_items[:8]
        while self._history_lay.count():
            item = self._history_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for item in self._history_items:
            time_text, payload = item.split(" • ", 1)
            self._history_lay.addWidget(self._history_entry(time_text, payload))
        self._history_lay.addStretch(1)
        self._convo_hint.setText(text)

    def _update_recommendations(self):
        pass

    def _on_tick(self):
        now = QDateTime.currentDateTime()
        self._time_chip._value_lbl.setText(now.toString("hh:mm"))  # type: ignore[attr-defined]
        self._status_chip._value_lbl.setText("ONLINE")  # type: ignore[attr-defined]
        self._weather_chip._value_lbl.setText("Clear")  # type: ignore[attr-defined]
        self._temp_chip._value_lbl.setText("29°C")  # type: ignore[attr-defined]

        if self._voice_state in ("Listening", "Thinking", "Executing"):
            for idx, bar in enumerate(self._voice_bars):
                height = 10 + int(12 + 12 * abs(((self._scan_phase + idx) % 8) - 4))
                bar.setFixedHeight(min(34, max(12, height)))
                bar.setStyleSheet(
                    f"background: {'rgba(255,69,69,0.22)' if self._voice_state == 'Listening' else 'rgba(79,195,255,0.22)' if self._voice_state == 'Thinking' else 'rgba(255,209,102,0.22)'}; border-radius: 3px;"
                )
            self._scan_phase += 1
        else:
            for bar in self._voice_bars:
                bar.setFixedHeight(12)
                bar.setStyleSheet("background: rgba(255,255,255,0.10); border-radius: 3px;")

        if self._scan_active:
            states = ["Scanning for devices.", "Scanning for devices..", "Scanning for devices..."]
            self._scan_status_lbl.setText(states[self._scan_phase % len(states)])
            if self._scan_phase > 5:
                self._scan_active = False
                self._scan_status_lbl.setText("4 devices discovered")
                self._record_history("Device discovery completed")
        self._metric_devices.set_value("18", "16 online", 89)
        self._metric_rooms.set_value("6", "Bedroom • Living Room • Kitchen", 72)
        self._metric_energy.set_value("2.9 kWh", "Today usage", 64)
