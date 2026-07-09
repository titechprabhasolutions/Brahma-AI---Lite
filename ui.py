from __future__ import annotations

import json
import html as html_lib
import math
import os
import platform
import random
import re
import sys
import threading
import time
from collections import deque
from pathlib import Path

import psutil
if platform.system() == "Windows":
    import winreg

from PyQt6.QtCore import (
    QEasingCurve, QEvent, QMimeData, QObject, QPoint, QPointF, QRectF, QSize, Qt,
    QTimer, QUrl, QPropertyAnimation, pyqtProperty, pyqtSignal,
)
from PyQt6.QtGui import (
    QAction, QBrush, QColor, QDragEnterEvent, QDropEvent, QFont, QFontDatabase,
    QIcon, QImage, QKeySequence, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
    QRadialGradient, QShortcut, QTextOption,
)
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QFrame, QGraphicsOpacityEffect, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMenu, QMainWindow, QPushButton, QScrollArea, QSizePolicy, QTextBrowser, QTextEdit,
    QGraphicsDropShadowEffect,
    QStyle, QSystemTrayIcon, QVBoxLayout, QWidget, QProgressBar,
    QStackedWidget, QInputDialog,
)

from discord_bot import DiscordBotService
from gesture_utils import estimate_gesture_state
from smart_home_page_new import BrahmaHomePage
from workspace_store import store as workspace_store

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR   = _base_dir()
CONFIG_DIR = BASE_DIR / "config"
API_FILE   = CONFIG_DIR / "api_keys.json"
APP_SETTINGS_FILE = CONFIG_DIR / "app_settings.json"
DISCORD_SETTINGS_FILE = CONFIG_DIR / "discord_bot.json"
LOGO_FILE  = BASE_DIR / "assets" / "Brahma_Lite_Logo.png"
LOGO_ICO   = BASE_DIR / "assets" / "Brahma_Lite_Logo.ico"
BACKGROUND_IMAGE_FILE = BASE_DIR / "assets" / "background.png"
MODEL_DOWNLOAD_URL = "https://storage.googleapis.com/mediapipe-assets/hand_landmarker.task"

_DEFAULT_W, _DEFAULT_H = 1500, 840
_MIN_W,     _MIN_H     = 1180, 720
_LEFT_W  = 270
_RIGHT_W = 430

_OS = platform.system()  # "Windows" | "Darwin" | "Linux"


class C:
    BG        = "#020305"
    PANEL     = "#07080b"
    PANEL2    = "#0d0f14"
    BORDER    = "#22252d"
    BORDER_B  = "#41454f"
    BORDER_A  = "#2b2e36"
    PRI       = "#ff4545"
    PRI_DIM   = "#ff7777"
    PRI_GHO   = "#2a0b0d"
    ACC       = "#ff4545"
    ACC2      = "#f8fbff"
    GREEN     = "#37ff5f"
    GREEN_D   = "#1dcc43"
    RED       = "#ff4545"
    MUTED_C   = "#ff4545"
    TEXT      = "#f4f6f8"
    TEXT_DIM  = "#8e949d"
    TEXT_MED  = "#c5cad2"
    WHITE     = "#ffffff"
    DARK      = "#000000"
    BAR_BG    = "#222222"


class BackgroundWidget(QWidget):
    def __init__(self, image_path: Path | str | None = None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        self._image_path = Path(image_path) if image_path else None
        self._background_pixmap = None
        self._load_background()

    def _load_background(self) -> None:
        if not self._image_path:
            return
        try:
            pix = QPixmap(str(self._image_path))
            if not pix.isNull():
                self._background_pixmap = pix
        except Exception:
            self._background_pixmap = None

    def paintEvent(self, event):
        if not self._background_pixmap:
            super().paintEvent(event)
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = self.rect()
        pix = self._background_pixmap.scaled(
            rect.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (rect.width() - pix.width()) // 2
        y = (rect.height() - pix.height()) // 2
        painter.drawPixmap(x, y, pix)
        painter.fillRect(rect, QColor(2, 3, 5, 28))
        painter.end()
        return


class RemoteKeyOverlay(QWidget):
    closed = pyqtSignal()

    def __init__(self, url: str, key: str, auto: str, manual: str, parent=None):
        super().__init__(parent)
        self._on_new_key = None
        self._manual_url = manual or url
        self._auto_login_url = auto or url
        self._expiry = time.time() + 600

        # larger opaque panel with neon red glow
        frame = QFrame(self)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(18, 20, 18, 18)
        lay.setSpacing(12)
        # Make overlay large and opaque so it pops
        try:
            self.setFixedSize(560, 680)
            frame.setFixedSize(self.size())
        except Exception:
            self.setFixedSize(520, 640)
            frame.setFixedSize(self.size())
        frame.setStyleSheet(f"""
            QFrame {{
                background: rgba(8,10,12,245);
                border: 2px solid {C.PRI};
                border-radius: 16px;
            }}
        """)
        # neon glow effect
        try:
            glow = QGraphicsDropShadowEffect(self)
            glow.setBlurRadius(48)
            glow.setColor(QColor(255,69,69,200))
            glow.setOffset(0, 0)
            frame.setGraphicsEffect(glow)
        except Exception:
            pass

        title = QLabel("Mobile Connect")
        title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        title.setStyleSheet("color: #fff; background: transparent;")
        lay.addWidget(title)

        subtitle = QLabel("Scan the QR code with your phone to connect.")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setFont(QFont("Segoe UI", 9))
        subtitle.setStyleSheet(f"color: {C.TEXT_DIM};")
        lay.addWidget(subtitle)

        self._qr_label = QLabel()
        self._qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._qr_label.setFixedSize(240, 240)
        self._qr_label.setStyleSheet("background: white; border-radius: 16px; padding: 8px;")
        qr_row = QHBoxLayout()
        qr_row.addStretch()
        qr_row.addWidget(self._qr_label)
        qr_row.addStretch()
        lay.addLayout(qr_row)

        manual_hint = QLabel("Manual address")
        manual_hint.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        manual_hint.setStyleSheet(f"color: {C.TEXT_DIM};")
        lay.addWidget(manual_hint)

        self._url_lbl = QLabel(self._manual_url)
        self._url_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._url_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._url_lbl.setFont(QFont("Consolas", 9))
        self._url_lbl.setStyleSheet(f"color: {C.TEXT_MED};")
        lay.addWidget(self._url_lbl)

        self._key_lbl = QLabel(key)
        self._key_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._key_lbl.setFont(QFont("Consolas", 34, QFont.Weight.Black))
        self._key_lbl.setStyleSheet(f"""
            color: {C.WHITE};
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(40,6,6,220), stop:1 rgba(60,8,8,220));
            border: 2px solid {C.PRI};
            border-radius: 12px;
            padding: 12px;
            letter-spacing: 12px;
            font-weight: 900;
        """)
        lay.addWidget(self._key_lbl)

        self._timer_lbl = QLabel("")
        self._timer_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._timer_lbl.setFont(QFont("Segoe UI", 8))
        self._timer_lbl.setStyleSheet(f"color: {C.TEXT_DIM};")
        lay.addWidget(self._timer_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self._new_btn = QPushButton("NEW KEY")
        self._new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._new_btn.setFixedHeight(34)
        self._new_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._new_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,69,69,22);
                color: {C.WHITE};
                border: 1px solid {C.PRI};
                border-radius: 8px;
            }}
            QPushButton:hover {{ background: rgba(255,69,69,44); }}
        """)
        self._new_btn.clicked.connect(self._refresh_key)
        btn_row.addWidget(self._new_btn)

        close_btn = QPushButton("CLOSE")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFixedHeight(34)
        close_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(12,14,18,238);
                color: {C.TEXT_MED};
                border: 1px solid {C.BORDER_B};
                border-radius: 8px;
            }}
            QPushButton:hover {{ color: {C.WHITE}; border: 1px solid {C.PRI}; }}
        """)
        close_btn.clicked.connect(self._do_close)
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        self._ctimer = QTimer(self)
        self._ctimer.timeout.connect(self._tick)
        self._ctimer.start(1000)
        self._update_qr(self._auto_login_url)
        self._tick()

        # Ensure the overlay has a sensible default size so positioning works.
        self.adjustSize()
        try:
            self.setFixedSize(max(360, self.width()), max(360, self.height()))
        except Exception:
            self.setFixedSize(420, 520)

    def set_new_key_callback(self, fn) -> None:
        self._on_new_key = fn

    def _update_qr(self, url: str) -> None:
        if not url:
            self._qr_label.setText("NO URL")
            return
        try:
            import qrcode
            from io import BytesIO
            qr = qrcode.QRCode(box_size=5, border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = BytesIO()
            img.save(buf, format="PNG")
            pix = QPixmap()
            pix.loadFromData(buf.getvalue())
            self._qr_label.setPixmap(pix.scaled(172, 172, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        except ImportError:
            self._qr_label.setText("Install\nqrcode[pil]")
            self._qr_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self._qr_label.setStyleSheet("color: #111; background: white; border-radius: 12px; padding: 6px;")
        except Exception:
            self._qr_label.setText("QR failed")

    def _tick(self):
        remaining = max(0, int(self._expiry - time.time()))
        mins, secs = divmod(remaining, 60)
        self._timer_lbl.setText(f"Key expires in {mins:02d}:{secs:02d}")
        if remaining <= 0:
            self._do_close()

    def mark_connected(self) -> None:
        self._ctimer.stop()
        self._key_lbl.setText("CONNECTED")
        self._key_lbl.setStyleSheet(f"""
            color: {C.GREEN};
            background: rgba(55,255,95,20);
            border: 1px solid rgba(55,255,95,150);
            border-radius: 10px;
            padding: 8px;
            letter-spacing: 4px;
        """)
        self._qr_label.setText("OK")
        self._qr_label.setFont(QFont("Segoe UI", 34, QFont.Weight.Black))
        self._qr_label.setStyleSheet("color: #37ff5f; background: #041006; border-radius: 12px;")
        self._timer_lbl.setText("Phone connected. Brahma remote is ready.")

    def _refresh_key(self):
        if not self._on_new_key:
            return
        result = self._on_new_key()
        if not result:
            return
        url = result[0]
        key = result[1]
        auto = result[2] if len(result) >= 3 else url
        manual = result[3] if len(result) >= 4 else url
        self._manual_url = manual or url
        self._auto_login_url = auto or url
        self._url_lbl.setText(self._manual_url)
        self._key_lbl.setText(key)
        self._key_lbl.setStyleSheet(f"""
            color: {C.WHITE};
            background: rgba(255,69,69,28);
            border: 1px solid {C.PRI};
            border-radius: 10px;
            padding: 8px;
            letter-spacing: 9px;
        """)
        self._update_qr(self._auto_login_url)
        self._expiry = time.time() + 600
        self._ctimer.start(1000)
        self._tick()

    def _do_close(self):
        self._ctimer.stop()
        self.hide()
        self.closed.emit()


def qcol(h: str, a: int = 255) -> QColor:
    c = QColor(h); c.setAlpha(a); return c


def _logo_icon() -> QIcon:
    return QIcon(str(LOGO_ICO if LOGO_ICO.exists() else LOGO_FILE))


def _logo_pixmap(size: int) -> QPixmap:
    pix = QPixmap(str(LOGO_FILE))
    if pix.isNull():
        return QPixmap(size, size)
    return pix.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


def _framed_logo(size: int, icon_size: int | None = None, *, bg: str = "rgba(18,18,18,240)",
                 border: str = None, radius: int | None = None, inset: int = 6) -> QFrame:
    border = border or C.BORDER_B
    radius = radius if radius is not None else max(10, size // 4)
    icon_size = icon_size or max(8, size - inset * 2)
    frame = QFrame()
    frame.setFixedSize(size, size)
    frame.setStyleSheet(
        f"background: {bg}; border: 1px solid {border}; border-radius: {radius}px;"
    )
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(inset, inset, inset, inset)
    lay.setSpacing(0)
    lbl = QLabel()
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setPixmap(_logo_pixmap(icon_size))
    lbl.setStyleSheet("background: transparent; border: none;")
    lay.addWidget(lbl)
    return frame


def _icon_pixmap(kind: str, size: int = 18) -> QPixmap:
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(qcol(C.WHITE), max(2.2, size * 0.14), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    if kind == "attach":
        # More readable paperclip shape
        p.drawArc(QRectF(size*0.22, size*0.14, size*0.42, size*0.58), 35*16, 290*16)
        p.drawArc(QRectF(size*0.42, size*0.24, size*0.28, size*0.44), 35*16, 290*16)
        p.drawLine(QPointF(size*0.28, size*0.56), QPointF(size*0.38, size*0.66))
    elif kind == "mic":
        # Clearer microphone silhouette
        p.drawRoundedRect(QRectF(size*0.31, size*0.14, size*0.38, size*0.48), size*0.16, size*0.16)
        p.drawLine(QPointF(size*0.50, size*0.62), QPointF(size*0.50, size*0.83))
        p.drawLine(QPointF(size*0.36, size*0.83), QPointF(size*0.64, size*0.83))
        p.drawLine(QPointF(size*0.42, size*0.70), QPointF(size*0.58, size*0.70))
    elif kind == "send":
        p.drawLine(QPointF(size*0.20, size*0.50), QPointF(size*0.70, size*0.50))
        p.drawLine(QPointF(size*0.48, size*0.30), QPointF(size*0.70, size*0.50))
        p.drawLine(QPointF(size*0.48, size*0.70), QPointF(size*0.70, size*0.50))

    p.end()
    return px


def _attach_pulse_glow(widget: QWidget, *, color: str = C.WHITE, blur_min: float = 12.0,
                       blur_max: float = 28.0, alpha: int = 180, period_ms: int = 2400) -> None:
    # Intentionally disabled for performance. Kept as a no-op so existing calls
    # do not need to change across the UI.
    return


def _quiet_run(*args, **kwargs):
    if _OS == "Windows":
        kwargs.setdefault("creationflags", getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return subprocess.run(*args, **kwargs)


def _quote_cmd_arg(path: str) -> str:
    return f'"{path}"'


def _hidden_launch_args(*extra_args: str) -> list[str]:
    pythonw = Path(r"C:\Users\ravit\AppData\Local\Programs\Python\Python313\pythonw.exe")
    python = Path(sys.executable)
    main_py = BASE_DIR / "main.py"
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable)
        return [str(exe), *extra_args]
    if pythonw.exists():
        return [str(pythonw), str(main_py), *extra_args]
    return [str(python), str(main_py), *extra_args]

def _startup_run_value() -> str:
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable)
        return f'{_quote_cmd_arg(str(exe))} --startup'
    pythonw = Path(r"C:\Users\ravit\AppData\Local\Programs\Python\Python313\pythonw.exe")
    main_py = BASE_DIR / "main.py"
    if pythonw.exists():
        return f'{_quote_cmd_arg(str(pythonw))} {_quote_cmd_arg(str(main_py))} --startup'
    return f'{_quote_cmd_arg(sys.executable)} {_quote_cmd_arg(str(main_py))} --startup'


def _startup_registry_key():
    if platform.system() != "Windows":
        return None
    return r"Software\Microsoft\Windows\CurrentVersion\Run"


def _current_boot_stamp() -> int:
    try:
        return int(psutil.boot_time())
    except Exception:
        return int(time.time())


def _launched_from_windows_startup() -> bool:
    return any(str(arg).strip().lower() == "--startup" for arg in sys.argv[1:])


def _default_app_settings() -> dict:
    return {
        "startup_animation_enabled": True,
        "last_boot_stamp": 0,
        "boot_sequence_played": False,
        "show_workspace_on_startup": False,
        "launcher_pos": None,
        "launch_minimized": False,
        "check_updates_on_startup": True,
        "default_ai_provider": "Gemini",
        "auto_provider_switch": True,
        "attention_message_prompts": True,
        "attention_call_prompts": True,
    }


def _default_discord_settings() -> dict:
    return {
        "bot_token": "",
        "enabled": False,
        "channel_id": "",
    }

class _SysMetrics:
    def __init__(self):
        self.cpu  = 0.0
        self.mem  = 0.0
        self.net  = 0.0   
        self.gpu  = -1.0  
        self.tmp  = -1.0  
        self._lock = threading.Lock()
        self._last_net = psutil.net_io_counters()
        self._last_net_t = time.time()
        self._running = True
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        while self._running:
            try:
                self._update()
            except Exception:
                pass
            time.sleep(1.5)

    def _update(self):
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent

        nc  = psutil.net_io_counters()
        now = time.time()
        dt  = now - self._last_net_t
        if dt > 0:
            sent = (nc.bytes_sent - self._last_net.bytes_sent) / dt
            recv = (nc.bytes_recv - self._last_net.bytes_recv) / dt
            net  = (sent + recv) / (1024 * 1024)
        else:
            net = 0.0
        self._last_net   = nc
        self._last_net_t = now

        gpu = self._get_gpu()

        tmp = self._get_temp()

        with self._lock:
            self.cpu = cpu
            self.mem = mem
            self.net = net
            self.gpu = gpu
            self.tmp = tmp

    def _get_gpu(self) -> float:
        # NVIDIA
        try:
            r = _quiet_run(
                ["nvidia-smi", "--query-gpu=utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2
            )
            if r.returncode == 0:
                vals = [float(v.strip()) for v in r.stdout.strip().split("\n") if v.strip()]
                if vals:
                    return sum(vals) / len(vals)
        except Exception:
            pass

        # AMD (Linux)
        if _OS == "Linux":
            try:
                r = _quiet_run(
                    ["rocm-smi", "--showuse", "--csv"],
                    capture_output=True, text=True, timeout=2
                )
                if r.returncode == 0:
                    for line in r.stdout.strip().split("\n"):
                        parts = line.split(",")
                        if len(parts) >= 2:
                            try:
                                return float(parts[1].strip().replace("%", ""))
                            except ValueError:
                                pass
            except Exception:
                pass

            # Intel GPU (Linux)
            try:
                r = _quiet_run(
                    ["intel_gpu_top", "-J", "-s", "500"],
                    capture_output=True, text=True, timeout=1
                )
                if r.returncode == 0 and "Render/3D" in r.stdout:
                    import re
                    m = re.search(r'"busy":\s*([\d.]+)', r.stdout)
                    if m:
                        return float(m.group(1))
            except Exception:
                pass

        # macOS â€” powermetrics (GPU Engine)
        if _OS == "Darwin":
            try:
                r = _quiet_run(
                    ["sudo", "-n", "powermetrics", "-n", "1", "-i", "500",
                     "--samplers", "gpu_power"],
                    capture_output=True, text=True, timeout=2
                )
                if r.returncode == 0 and "GPU" in r.stdout:
                    import re
                    m = re.search(r'GPU\s+Active:\s+([\d.]+)%', r.stdout)
                    if m:
                        return float(m.group(1))
            except Exception:
                pass

        return -1.0

    def _get_temp(self) -> float:
        try:
            temps = psutil.sensors_temperatures()
            candidates = ["coretemp", "k10temp", "cpu_thermal", "acpitz",
                          "cpu-thermal", "zenpower", "it8688"]
            for name in candidates:
                if name in temps:
                    entries = temps[name]
                    if entries:
                        return entries[0].current
            for entries in temps.values():
                if entries:
                    return entries[0].current
        except Exception:
            pass
        if _OS == "Darwin":
            try:
                r = _quiet_run(
                    ["osx-cpu-temp"], capture_output=True, text=True, timeout=2
                )
                if r.returncode == 0:
                    import re
                    m = re.search(r"([\d.]+)", r.stdout)
                    if m:
                        return float(m.group(1))
            except Exception:
                pass

        if _OS == "Windows":
            try:
                r = _quiet_run(
                    ["powershell", "-Command",
                     "(Get-WmiObject MSAcpi_ThermalZoneTemperature -Namespace root/wmi).CurrentTemperature"],
                    capture_output=True, text=True, timeout=3
                )
                if r.returncode == 0 and r.stdout.strip():
                    raw = float(r.stdout.strip().split("\n")[0])
                    return (raw / 10.0) - 273.15
            except Exception:
                pass

        return -1.0

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "cpu": self.cpu,
                "mem": self.mem,
                "net": self.net,
                "gpu": self.gpu,
                "tmp": self.tmp,
            }


_metrics = _SysMetrics()

_CAM_OK_CACHE = {"ok": False, "ts": 0.0}


def _camera_available() -> bool:
    now = time.time()
    if now - _CAM_OK_CACHE["ts"] < 10.0:
        return bool(_CAM_OK_CACHE["ok"])

    ok = False
    cap = None
    try:
        import cv2  # optional dependency; used only for a quick camera probe

        indices = [0, 1, 2]
        if _OS == "Windows":
            for idx in indices:
                try:
                    cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                    if cap.isOpened():
                        ret, frame = cap.read()
                        if ret and frame is not None:
                            ok = True
                            break
                finally:
                    if cap is not None:
                        cap.release()
                        cap = None
        else:
            cap = cv2.VideoCapture(0)
            if cap.isOpened():
                ret, frame = cap.read()
                ok = bool(ret and frame is not None)
    except Exception:
        ok = False
    finally:
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass

    _CAM_OK_CACHE["ok"] = ok
    _CAM_OK_CACHE["ts"] = now
    return ok


class _GestureRenderCanvas(QWidget):
    CONNECTIONS = [
        (0, 1), (1, 2), (2, 3), (3, 4),
        (0, 5), (5, 6), (6, 7), (7, 8),
        (5, 9), (9, 10), (10, 11), (11, 12),
        (9, 13), (13, 14), (14, 15), (15, 16),
        (13, 17), (17, 18), (18, 19), (19, 20),
        (0, 17)
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAutoFillBackground(False)
        self._landmarks: list[tuple[float, float, float]] = []
        self._hand_visible = False
        self._search_phase = 0
        self._target_opacity = 0.0
        self._skeleton_opacity = 0.0

    def set_landmarks(self, landmarks: list[tuple[float, float, float]]):
        self._landmarks = landmarks or []
        self.update()

    def set_hand_visible(self, visible: bool):
        self._hand_visible = visible
        self._target_opacity = 1.0 if visible else 0.0
        self.update()

    def set_search_phase(self, phase: int):
        self._search_phase = phase
        self.update()

    def _normalized_points(self, rect: QRectF) -> list[QPointF]:
        if not self._landmarks:
            return []
        xs = [p[0] for p in self._landmarks]
        ys = [p[1] for p in self._landmarks]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        bbox_w = max_x - min_x
        bbox_h = max_y - min_y
        if bbox_w < 1e-4:
            bbox_w = 1e-4
        if bbox_h < 1e-4:
            bbox_h = 1e-4
        avail_w = rect.width() * 0.82
        avail_h = rect.height() * 0.82
        scale = min(avail_w / bbox_w, avail_h / bbox_h)
        center_x = rect.center().x()
        center_y = rect.center().y()
        mid_x = (min_x + max_x) / 2.0
        mid_y = (min_y + max_y) / 2.0
        points: list[QPointF] = []
        for x, y, _ in self._landmarks:
            px = center_x + (x - mid_x) * scale
            py = center_y + (y - mid_y) * scale
            points.append(QPointF(px, py))
        return points

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        painter.fillRect(rect, QColor(3, 4, 7))

        if self._hand_visible and len(self._landmarks) >= 21:
            # animate opacity toward target
            self._skeleton_opacity += (self._target_opacity - self._skeleton_opacity) * 0.24
            pts = self._normalized_points(rect)
            if pts:
                # soft glow
                glow_pen = QPen(QColor(255, 70, 70, int(120 * self._skeleton_opacity)), 18,
                                Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                painter.setPen(glow_pen)
                for a, b in self.CONNECTIONS:
                    painter.drawLine(pts[a], pts[b])

                edge_pen = QPen(QColor(255, 110, 110, int(220 * self._skeleton_opacity)), 4,
                               Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                painter.setPen(edge_pen)
                for a, b in self.CONNECTIONS:
                    painter.drawLine(pts[a], pts[b])

                for point in pts:
                    radius = 7.0
                    grad = QRadialGradient(point, radius * 2.2)
                    grad.setColorAt(0.0, QColor(255, 255, 255, int(240 * self._skeleton_opacity)))
                    grad.setColorAt(0.15, QColor(255, 130, 130, int(180 * self._skeleton_opacity)))
                    grad.setColorAt(1.0, QColor(255, 30, 30, int(16 * self._skeleton_opacity)))
                    painter.setBrush(QBrush(grad))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(point, radius * 1.4, radius * 1.4)
                    painter.setBrush(QColor(255, 255, 255, int(230 * self._skeleton_opacity)))
                    painter.drawEllipse(point, 3.5, 3.5)
        else:
            self._skeleton_opacity += (self._target_opacity - self._skeleton_opacity) * 0.24
            dot_count = (self._search_phase // 8) % 4
            message = "Searching for hand" + ("." * dot_count)
            painter.setPen(QColor(200, 200, 220, 180))
            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, message)

        painter.end()


class GestureCameraPreview(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GestureCameraPreview")
        self.setStyleSheet(
            f"""
            QFrame#GestureCameraPreview {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(9, 10, 14, 255),
                    stop:1 rgba(3, 4, 7, 255));
                border: 1px solid rgba(255, 69, 69, 0.24);
                border-radius: 16px;
            }}
            QLabel {{ background: transparent; }}
            """
        )
        self._cap = None
        self._timer = None
        self._hands = None
        self._use_tasks_api = False
        self._vision_module = None
        self._prev_pinch = False
        self._smoothed_cursor: tuple[float, float] | None = None
        self._smoothed_screen: tuple[float, float] | None = None
        self._smoothed_landmarks: list[tuple[float, float, float]] | None = None
        self._search_phase = 0
        self._smoothing_alpha = 0.8
        self._gesture_canvas_alpha = 0.0
        self._sensitivity = 1.0
        self._sensitivity_levels = {"Low": 0.8, "Medium": 1.0, "High": 1.4}
        self._invert_cursor_x = False
        self._invert_cursor_y = False
        self._cursor_calibration_x_min: float | None = None
        self._cursor_calibration_x_max: float | None = None
        self._cursor_calibration_y_min: float | None = None
        self._cursor_calibration_y_max: float | None = None
        self._last_screen_pos: tuple[int, int] | None = None
        self._cursor_anchor: tuple[float, float] | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(10)

        title = QLabel("HAND TRACKING")
        title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.WHITE}; letter-spacing: 1px;")
        header_row.addWidget(title)
        header_row.addStretch(1)

        self._status_dot = QLabel()
        self._status_dot.setFixedSize(12, 12)
        self._status_dot.setStyleSheet("border-radius: 6px; background: #ffb347;")
        header_row.addWidget(self._status_dot)

        self._status_text = QLabel("SEARCHING")
        self._status_text.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self._status_text.setStyleSheet("color: #ffb347;")
        header_row.addWidget(self._status_text)

        self._sensitivity_select = QComboBox()
        self._sensitivity_select.addItems(["Low", "Medium", "High"])
        self._sensitivity_select.setCurrentText("Medium")
        self._sensitivity_select.setFixedWidth(84)
        self._sensitivity_select.setStyleSheet(
            "QComboBox { background: rgba(255,255,255,0.05); color: #f4f6f8; border: 1px solid rgba(255,69,69,0.24); border-radius: 8px; padding: 4px 8px; }"
            "QComboBox::drop-down { border: none; }")
        self._sensitivity_select.currentTextChanged.connect(self._set_sensitivity_level)
        header_row.addWidget(self._sensitivity_select)
        lay.addLayout(header_row)

        self._hand_canvas = _GestureRenderCanvas(self)
        self._hand_canvas.setFixedHeight(220)
        self._hand_canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay.addWidget(self._hand_canvas)

        self._status_hint_label = QLabel("Initializing hand detection...")
        self._status_hint_label.setFont(QFont("Segoe UI", 8))
        self._status_hint_label.setStyleSheet(f"color: {C.TEXT_DIM};")
        self._status_hint_label.setWordWrap(True)
        lay.addWidget(self._status_hint_label)

        footer = QGridLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setHorizontalSpacing(16)
        footer.setVerticalSpacing(8)

        self._status_value = QLabel("Searching")
        self._confidence_value = QLabel("0%")
        self._gesture_value = QLabel("None")
        self._cursor_value = QLabel("Inactive")

        for idx, (label_text, value_label) in enumerate([
            ("Status", self._status_value),
            ("Confidence", self._confidence_value),
            ("Gesture", self._gesture_value),
            ("Cursor", self._cursor_value),
        ]):
            label = QLabel(label_text.upper())
            label.setFont(QFont("Segoe UI", 7, QFont.Weight.DemiBold))
            label.setStyleSheet(f"color: {C.TEXT_DIM};")
            value_label.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            value_label.setStyleSheet(f"color: {C.WHITE};")
            footer.addWidget(label, idx, 0)
            footer.addWidget(value_label, idx, 1)

        lay.addLayout(footer)

        self._expanded_height = 320
        self._collapsed_height = 64

        try:
            self.setFixedHeight(self._expanded_height)
        except Exception:
            pass

        self._set_status("Searching for hand...", "searching")
        self._start_camera()

    def closeEvent(self, event):
        self._stop_camera()
        super().closeEvent(event)

    def mousePressEvent(self, event):
        try:
            if event.button() == Qt.MouseButton.LeftButton:
                self._toggle_camera()
                event.accept()
                return
        except Exception:
            pass
        return super().mousePressEvent(event)

    def _set_status(self, text: str, level: str = "searching"):
        self._status_hint_label.setText(text)
        self._status_value.setText(level.capitalize())
        colors = {
            "tracking": C.GREEN,
            "searching": "#ffb347",
            "lost": C.RED,
        }
        color = colors.get(level, "#ffb347")
        self._status_dot.setStyleSheet(f"border-radius: 6px; background: {color};")
        self._status_text.setText(level.upper())
        self._status_text.setStyleSheet(f"color: {color};")

    def _start_camera(self):
        if self._cap is not None:
            return
        try:
            import cv2
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW if hasattr(cv2, "CAP_DSHOW") else cv2.CAP_ANY)
            try:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
            except Exception:
                pass
            if not cap.isOpened():
                cap.release()
                raise RuntimeError("camera unavailable")
            self._cap = cap
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._tick)
            self._timer.start(30)
            self._set_status("Camera ready. Move your hand to steer the cursor.", "searching")
            try:
                import pyautogui
                pyautogui.FAILSAFE = False
            except Exception:
                pass
        except Exception as exc:
            self._set_status(f"Gesture camera is offline: {exc}", "lost")

        if self._cap is not None:
            try:
                self.setFixedHeight(self._expanded_height)
            except Exception:
                pass

    def _stop_camera(self):
        if self._timer is not None:
            self._timer.stop()
            self._timer.deleteLater()
            self._timer = None
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None
        if self._hands is not None:
            try:
                self._hands.close()
            except Exception:
                pass
            self._hands = None

        try:
            self.setFixedHeight(self._collapsed_height)
        except Exception:
            pass
        self._set_status("Camera stopped", "lost")

    def _download_hand_landmarker_model(self, model_path: Path) -> bool:
        temp_path = model_path.with_suffix(model_path.suffix + ".download")
        try:
            import urllib.request

            self._set_status("Downloading gesture model...", "searching")
            model_path.parent.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(MODEL_DOWNLOAD_URL, timeout=60) as response:
                with open(temp_path, "wb") as out_file:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        out_file.write(chunk)
            temp_path.replace(model_path)
            return True
        except Exception as exc:
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass
            self._set_status(
                f"Gesture model download failed: {exc}. "
                f"Put hand_landmarker.task into {model_path.parent} and restart.",
                "lost",
            )
            return False

    def _tick(self):
        if self._cap is None:
            return
        try:
            ret, frame = self._cap.read()
            if not ret or frame is None:
                self._set_status("Camera feed dropped. Trying again…", "lost")
                return
            self._process_frame(frame)
        except Exception as exc:
            self._set_status(f"Gesture camera error: {exc}", "lost")

    def _process_frame(self, frame):
        try:
            import cv2
        except Exception as exc:
            self._set_status(f"Gesture camera unavailable: {exc}", "lost")
            return

        import importlib

        mp = None
        try:
            mp = importlib.import_module("mediapipe")
        except Exception:
            pass

        if mp is None:
            self._set_status(
                "Gesture camera unavailable: mediapipe not found. "
                "Install it into the app venv: .venv\\Scripts\\python.exe -m pip install mediapipe",
                "lost",
            )
            return

        if self._hands is None:
            HandsClass = None
            try:
                solutions = getattr(mp, "solutions", None)
                if solutions is not None and hasattr(solutions, "hands"):
                    HandsClass = solutions.hands.Hands
            except Exception:
                HandsClass = None

            if HandsClass is not None:
                try:
                    self._hands = HandsClass(
                        static_image_mode=False,
                        max_num_hands=1,
                        min_detection_confidence=0.5,
                        min_tracking_confidence=0.5,
                    )
                    self._use_tasks_api = False
                except Exception as exc:
                    self._set_status(f"Gesture init error: {exc}", "lost")
                    return
            else:
                vision = None
                try:
                    vision = importlib.import_module("mediapipe.tasks.python.vision")
                except Exception:
                    vision = None

                if vision is None or not hasattr(vision, "HandLandmarker"):
                    self._set_status(
                        "Gesture camera unavailable: mediapipe Tasks API not available. "
                        "Install mediapipe into the app venv and restart.",
                        "lost",
                    )
                    return

                model_dir = CONFIG_DIR / "models"
                model_dir.mkdir(parents=True, exist_ok=True)
                model_path = model_dir / "hand_landmarker.task"
                if not model_path.exists():
                    self._set_status("Downloading model", "searching")
                    if not self._download_hand_landmarker_model(model_path):
                        return

                try:
                    self._hands = vision.HandLandmarker.create_from_model_path(str(model_path))
                    self._use_tasks_api = True
                    self._vision_module = vision
                except Exception as exc:
                    self._set_status(f"Gesture init error: {exc}", "lost")
                    return

        height, width = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        landmarks: list[tuple[float, float, float]] = []
        confidence = 0.0

        if self._use_tasks_api:
            try:
                import numpy as np
                image_lib = importlib.import_module("mediapipe.tasks.python.vision.core.image")
                mp_image = image_lib.Image(image_lib.ImageFormat.SRGB, np.ascontiguousarray(rgb))
                results = self._hands.detect(mp_image)
            except Exception as exc:
                self._set_status(f"Gesture task detect error: {exc}", "lost")
                return
            if getattr(results, "hand_landmarks", None):
                hand_landmarks = results.hand_landmarks[0]
                for landmark in hand_landmarks:
                    landmarks.append((landmark.x, landmark.y, landmark.z))
                confidence = 1.0 if landmarks else 0.0
        else:
            results = self._hands.process(rgb)
            if getattr(results, "multi_hand_landmarks", None):
                hand_landmarks = results.multi_hand_landmarks[0]
                for landmark in hand_landmarks.landmark:
                    landmarks.append((landmark.x, landmark.y, landmark.z))
            if getattr(results, "multi_handedness", None) and results.multi_handedness:
                try:
                    confidence = float(results.multi_handedness[0].classification[0].score)
                except Exception:
                    confidence = 1.0 if landmarks else 0.0

        gesture = estimate_gesture_state(landmarks, self._prev_pinch)
        if gesture.get("cursor"):
            norm = self._calibrate_and_smooth_cursor(gesture["cursor"])
            self._move_cursor(norm)
        if gesture.get("pinch_triggered"):
            self._trigger_click()
        self._prev_pinch = bool(gesture.get("pinch", False))

        self._render_hand(landmarks, gesture, confidence)

    def _render_hand(self, landmarks: list[tuple[float, float, float]], gesture: dict, confidence: float):
        has_hand = bool(landmarks and len(landmarks) >= 21)
        if has_hand:
            if self._smoothed_landmarks is None or len(self._smoothed_landmarks) != len(landmarks):
                self._smoothed_landmarks = landmarks.copy()
            else:
                alpha = 0.32
                smoothed: list[tuple[float, float, float]] = []
                for prev, current in zip(self._smoothed_landmarks, landmarks):
                    sx, sy, sz = prev
                    tx, ty, tz = current
                    smoothed.append((sx + alpha * (tx - sx), sy + alpha * (ty - sy), sz + alpha * (tz - sz)))
                self._smoothed_landmarks = smoothed
            self._hand_canvas.set_landmarks(self._smoothed_landmarks)
            self._hand_canvas.set_hand_visible(True)
            self._hand_canvas.set_search_phase(0)
            self._set_status("Hand detected and tracking.", "tracking")
            self._confidence_value.setText(f"{int(confidence * 100)}%")
            self._gesture_value.setText("Pinch" if gesture.get("pinch") else "Open Hand")
            self._cursor_value.setText("Active" if gesture.get("cursor") else "Inactive")
        else:
            self._hand_canvas.set_hand_visible(False)
            self._search_phase = (self._search_phase + 1) % 32
            self._hand_canvas.set_search_phase(self._search_phase)
            self._set_status("Searching for hand...", "searching")
            self._confidence_value.setText("0%")
            self._gesture_value.setText("None")
            self._cursor_value.setText("Inactive")

    def _calibrate_and_smooth_cursor(self, cursor: tuple[float, float]) -> tuple[float, float]:
        raw_x = float(cursor[0])
        raw_y = float(cursor[1])

        if self._invert_cursor_x:
            raw_x = 1.0 - raw_x
        if self._invert_cursor_y:
            raw_y = 1.0 - raw_y

        raw_x = max(0.0, min(1.0, raw_x))
        raw_y = max(0.0, min(1.0, raw_y))

        if self._cursor_anchor is None:
            self._cursor_anchor = (raw_x, raw_y)
            return (raw_x, raw_y)

        anchor_x, anchor_y = self._cursor_anchor
        mapped_x = raw_x
        mapped_y = raw_y

        if self._smoothed_cursor is None:
            self._smoothed_cursor = (mapped_x, mapped_y)
        else:
            sx, sy = self._smoothed_cursor
            a = self._smoothing_alpha
            self._smoothed_cursor = (sx + a * (mapped_x - sx), sy + a * (mapped_y - sy))

        return self._smoothed_cursor

    def _set_sensitivity_level(self, level: str) -> None:
        self._sensitivity = self._sensitivity_levels.get(level, self._sensitivity_levels["Medium"])

    def _move_cursor(self, cursor):
        try:
            import pyautogui
            screen = QApplication.primaryScreen()
            if screen is None:
                return
            geom = screen.geometry()
            if not geom.isValid():
                return

            try:
                s = float(self._sensitivity)
            except Exception:
                s = 1.0

            nx = float(cursor[0])
            ny = float(cursor[1])
            nx = max(0.0, min(1.0, nx))
            ny = max(0.0, min(1.0, ny))

            x = int(geom.left() + nx * geom.width())
            y = int(geom.top() + ny * geom.height())

            if self._smoothed_screen is None:
                self._smoothed_screen = (float(x), float(y))
            else:
                sx, sy = self._smoothed_screen
                a = max(0.18, min(0.36, self._smoothing_alpha))
                self._smoothed_screen = (sx + a * (x - sx), sy + a * (y - sy))

            target_x = int(round(self._smoothed_screen[0]))
            target_y = int(round(self._smoothed_screen[1]))
            dead_zone = max(3, int(min(geom.width(), geom.height()) * 0.004))

            if self._last_screen_pos is not None:
                last_x, last_y = self._last_screen_pos
                if abs(target_x - last_x) <= dead_zone and abs(target_y - last_y) <= dead_zone:
                    return

            self._last_screen_pos = (target_x, target_y)
            try:
                pyautogui.moveTo(target_x, target_y, duration=0)
            except Exception:
                pyautogui.moveTo(target_x, target_y, duration=0.01)
        except Exception:
            pass

    def _trigger_click(self):
        try:
            import pyautogui
            pyautogui.click(button="left")
        except Exception:
            pass

    def _toggle_camera(self):
        if self._cap is None:
            self._start_camera()
        else:
            self._stop_camera()


def _active_net_label() -> str:
    try:
        stats = psutil.net_if_stats()
        active = []
        for name, info in stats.items():
            if getattr(info, "isup", False):
                active.append(name)
        if active:
            return active[0]
    except Exception:
        pass
    return "No active adapter"

class HudCanvas(QWidget):
    def __init__(self, face_path: str, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.muted    = False
        self.speaking = False
        self.state    = "INITIALISING"

        self._tick       = 0
        self._scale      = 1.0
        self._tgt_scale  = 1.0
        self._halo       = 55.0
        self._tgt_halo   = 55.0
        self._last_t     = time.time()
        self._scan       = 0.0
        self._scan2      = 180.0
        self._rings      = [0.0, 120.0, 240.0]
        self._pulses: list[float] = [0.0, 50.0, 100.0]
        self._blink      = True
        self._blink_tick = 0
        self._particles: list[list[float]] = []
        self._face_px: QPixmap | None = None
        self._load_face(face_path)

        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._tmr.start(16)

    def _load_face(self, path: str):
        try:
            from PIL import Image, ImageDraw
            import io
            img = Image.open(path).convert("RGBA")
            sz  = min(img.size)
            img = img.resize((sz, sz), Image.LANCZOS)
            mk  = Image.new("L", (sz, sz), 0)
            ImageDraw.Draw(mk).ellipse((2, 2, sz - 2, sz - 2), fill=255)
            img.putalpha(mk)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            px = QPixmap(); px.loadFromData(buf.getvalue())
            self._face_px = px
        except Exception:
            self._face_px = None

    def _step(self):
        self._tick += 1
        now = time.time()
        if now - self._last_t > (0.12 if self.speaking else 0.5):
            if self.speaking:
                self._tgt_scale = random.uniform(1.06, 1.14)
                self._tgt_halo  = random.uniform(145, 190)
            elif self.muted:
                self._tgt_scale = random.uniform(0.998, 1.002)
                self._tgt_halo  = random.uniform(15, 28)
            elif self.state == "LISTENING":
                self._tgt_scale = random.uniform(1.008, 1.018)
                self._tgt_halo  = random.uniform(90, 122)
            elif self.state == "THINKING":
                self._tgt_scale = random.uniform(1.012, 1.024)
                self._tgt_halo  = random.uniform(78, 105)
            elif self.state in ("EXECUTING", "PROCESSING"):
                self._tgt_scale = random.uniform(1.016, 1.032)
                self._tgt_halo  = random.uniform(110, 148)
            else:
                self._tgt_scale = random.uniform(1.001, 1.008)
                self._tgt_halo  = random.uniform(48, 68)
            self._last_t = now

        sp = 0.38 if self.speaking else 0.15
        self._scale += (self._tgt_scale - self._scale) * sp
        self._halo  += (self._tgt_halo  - self._halo)  * sp

        speeds = [1.3, -0.9, 2.0] if self.speaking else [0.55, -0.35, 0.9]
        for i, spd in enumerate(speeds):
            self._rings[i] = (self._rings[i] + spd) % 360

        self._scan  = (self._scan  + (3.0 if self.speaking else 1.3)) % 360
        self._scan2 = (self._scan2 + (-2.0 if self.speaking else -0.75)) % 360

        fw  = min(self.width(), self.height())
        lim = fw * 0.74
        spd = 4.2 if self.speaking else 2.0
        self._pulses = [r + spd for r in self._pulses if r + spd < lim]
        if len(self._pulses) < 3 and random.random() < (0.07 if self.speaking else 0.025):
            self._pulses.append(0.0)

        if self.speaking and random.random() < 0.28:
            cx, cy = self.width() / 2, self.height() / 2
            ang = random.uniform(0, 2 * math.pi)
            r_s = fw * 0.28
            self._particles.append([
                cx + math.cos(ang) * r_s, cy + math.sin(ang) * r_s,
                math.cos(ang) * random.uniform(0.9, 2.4),
                math.sin(ang) * random.uniform(0.9, 2.4) - 0.4, 1.0,
            ])
        self._particles = [
            [p[0]+p[2], p[1]+p[3], p[2]*0.97, p[3]*0.97, p[4]-0.028]
            for p in self._particles if p[4] > 0
        ]

        self._blink_tick += 1
        if self._blink_tick >= 38:
            self._blink = not self._blink
            self._blink_tick = 0
        self.update()

    def _accent_color(self) -> QColor:
        if self.muted:
            return QColor(255, 69, 69, 255)
        if self.speaking:
            return QColor(255, 69, 69, 255)
        if self.state == "LISTENING":
            return QColor(69, 127, 255, 255)
        if self.state == "THINKING":
            return QColor(255, 185, 96, 255)
        if self.state in ("EXECUTING", "PROCESSING"):
            return QColor(255, 69, 69, 255)
        return QColor(255, 69, 69, 255)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(2, 3, 5, 20))

        accent = self._accent_color()
        W, H = self.width(), self.height()
        cx, cy = W / 2, H / 2
        fw = min(W, H)

        # fine tactical grid and red signal noise
        p.setPen(QPen(QColor(255, 255, 255, 8), 1))
        for x in range(0, W, 48):
            for y in range(0, H, 48):
                p.drawPoint(x, y)
        p.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 48), 1))
        for side in (-1, 1):
            base_x = cx + side * fw * 0.37
            base_y = cy
            for i in range(68):
                x = base_x + side * (i * 1.4)
                h = 4 + abs(math.sin(self._tick * 0.04 + i * 0.35)) * (8 + (i % 9) * 2)
                if i % 11 == 0:
                    h *= 1.8
                p.drawLine(QPointF(x, base_y - h), QPointF(x, base_y + h))
            p.drawLine(QPointF(base_x - side * 130, base_y), QPointF(base_x + side * 155, base_y))

        r_face = fw * 0.34

        # halo glow
        for i in range(10):
            r   = r_face * (1.8 - i * 0.08)
            frc = 1.0 - i / 10
            a   = max(0, min(255, int(self._halo * 0.055 * frc)))
            col = QColor(255, 69, 69, a)
            p.setPen(QPen(col, 1.2)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # pulse rings
        for pr in self._pulses:
            a   = max(0, int(230 * (1.0 - pr / (fw * 0.74))))
            col = QColor(255, 69, 69, a)
            p.setPen(QPen(col, 1.5)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - pr, cy - pr, pr * 2, pr * 2))

        # spinning arc rings
        for idx, (r_frac, w_r, arc_l, gap) in enumerate(
            [(0.48, 1.9, 115, 78), (0.42, 1.4, 78, 55), (0.35, 1.0, 56, 40)]
        ):
            ring_r = fw * r_frac
            base   = self._rings[idx]
            a_val  = max(0, min(180, int(self._halo * 0.45 * (1.0 - idx * 0.18))))
            col    = QColor(accent.red(), accent.green(), accent.blue(), a_val)
            p.setPen(QPen(col, w_r)); p.setBrush(Qt.BrushStyle.NoBrush)
            angle = base
            rect  = QRectF(cx - ring_r, cy - ring_r, ring_r * 2, ring_r * 2)
            while angle < base + 360:
                p.drawArc(rect, int(angle * 16), int(arc_l * 16))
                angle += arc_l + gap

        # scanners
        sr = fw * 0.50
        sa = min(200, int(self._halo * 0.8))
        ex = 75 if self.speaking else 44
        p.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), sa), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        srect = QRectF(cx - sr, cy - sr, sr * 2, sr * 2)
        p.drawArc(srect, int(self._scan * 16), int(ex * 16))
        p.setPen(QPen(QColor(255, 255, 255, max(28, sa // 4)), 1.0))
        p.drawArc(srect, int(self._scan2 * 16), int(ex * 16))

        # tick marks
        t_out, t_in = fw * 0.497, fw * 0.474
        p.setPen(QPen(QColor(245, 248, 255, 145), 1))
        for deg in range(0, 360, 10):
            rad = math.radians(deg)
            inn = t_in if deg % 30 == 0 else t_in + 6
            p.drawLine(
                QPointF(cx + t_out * math.cos(rad), cy - t_out * math.sin(rad)),
                QPointF(cx + inn  * math.cos(rad), cy - inn  * math.sin(rad)),
            )

        # crosshair
        ch_r, gap_h = fw * 0.51, fw * 0.16
        p.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), int(self._halo * 0.5)), 1))
        p.drawLine(QPointF(cx - ch_r, cy), QPointF(cx - gap_h, cy))
        p.drawLine(QPointF(cx + gap_h, cy), QPointF(cx + ch_r, cy))
        p.drawLine(QPointF(cx, cy - ch_r), QPointF(cx, cy - gap_h))
        p.drawLine(QPointF(cx, cy + gap_h), QPointF(cx, cy + ch_r))

        # corner brackets
        bl = 28
        bc = QColor(accent.red(), accent.green(), accent.blue(), 120)
        hl, hr = cx - fw // 2, cx + fw // 2
        ht, hb = cy - fw // 2, cy + fw // 2
        p.setPen(QPen(bc, 1.5))
        for bx, by, dx, dy in [(hl,ht,1,1),(hr,ht,-1,1),(hl,hb,1,-1),(hr,hb,-1,-1)]:
            p.drawLine(QPointF(bx, by), QPointF(bx + dx * bl, by))
            p.drawLine(QPointF(bx, by), QPointF(bx, by + dy * bl))

        # face text only: remove the center orb circle overlay
        title_font = QFont("Segoe UI", int(max(20, fw * 0.052)), QFont.Weight.Bold)
        p.setFont(title_font)
        y_title = cy - 25
        p.setPen(QColor(245, 248, 255, 235))
        p.drawText(QRectF(cx - 120, y_title, 130, 48), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "Brah")
        p.setPen(QColor(255, 98, 98, 245))
        p.drawText(QRectF(cx + 8, y_title, 90, 48), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "ma")
        p.setFont(QFont("Segoe UI", int(max(8, fw * 0.018)), QFont.Weight.Bold))
        p.setPen(QColor(190, 196, 205, 190))
        p.drawText(QRectF(cx - 90, cy + 18, 180, 22), Qt.AlignmentFlag.AlignCenter, "AI ASSISTANT")

        # keep the center clean: no extra particles

        # status text
        sy = cy + fw * 0.40
        if self.muted:
            txt, col = "MIC STATUS\nMUTED", QColor(255, 69, 69, 235)
        elif self.speaking:
            txt, col = "MIC STATUS\nSPEAKING", QColor(255, 255, 255, 235)
        elif self.state == "THINKING":
            txt, col = "AI CORE\nTHINKING", QColor(255, 185, 96, 235)
        elif self.state in ("PROCESSING", "EXECUTING"):
            txt, col = "AI CORE\nEXECUTING", QColor(255, 69, 69, 235)
        elif self.state == "LISTENING":
            txt, col = "MIC STATUS\nLISTENING", QColor(69, 127, 255, 220)
        else:
            txt, col = f"AI CORE\n{self.state}", QColor(255, 255, 255, 220)

        p.setPen(QPen(col, 1))
        p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        top_status, bottom_status = txt.split("\n", 1)
        p.drawText(QRectF(0, sy, W, 18), Qt.AlignmentFlag.AlignCenter, top_status)
        p.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        p.drawText(QRectF(0, sy + 18, W, 24), Qt.AlignmentFlag.AlignCenter, bottom_status)

        # waveform
        wy = sy + 30
        N, bw = 36, 8
        wx0 = (W - N * bw) / 2
        for i in range(N):
            if self.muted:
                hgt, cl = 2, qcol(C.MUTED_C)
            elif self.speaking:
                hgt = random.randint(3, 20)
                cl  = qcol(C.PRI) if hgt > 12 else qcol(C.PRI_DIM)
            else:
                hgt = int(3 + 2 * math.sin(self._tick * 0.09 + i * 0.6))
                cl  = QColor(accent.red(), accent.green(), accent.blue(), 90 if self.state == "LISTENING" else 60)
            p.fillRect(QRectF(wx0 + i * bw, wy + 20 - hgt, bw - 1, hgt), cl)

class MetricBar(QWidget):

    def __init__(self, label: str, color: str = C.PRI, parent=None):
        super().__init__(parent)
        self._label = label
        self._color = color
        self._value = 0.0       # 0â€“100
        self._text  = "--"
        self.setFixedHeight(38)
        self.setMinimumWidth(80)

    def set_value(self, pct: float, text: str):
        self._value = max(0.0, min(100.0, pct))
        self._text  = text
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        p.setBrush(QBrush(qcol(C.PANEL2)))
        p.setPen(QPen(qcol(C.BORDER_A), 1))
        p.drawRoundedRect(QRectF(1, 1, W - 2, H - 2), 4, 4)

        bar_h   = 4
        bar_y   = H - bar_h - 5
        bar_w   = W - 12
        bar_x   = 6
        fill_w  = int(bar_w * self._value / 100)

        p.setBrush(QBrush(qcol(C.BAR_BG)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 2, 2)

        if self._value > 85:
            bar_col = qcol(C.RED)
        elif self._value > 65:
            bar_col = qcol(C.ACC)
        else:
            bar_col = qcol(self._color)

        if fill_w > 0:
            p.setBrush(QBrush(bar_col))
            p.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 2, 2)

        p.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(8, 5, 50, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._label)

        p.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        p.setPen(QPen(bar_col if self._text != "--" else qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(0, 4, W - 6, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self._text)

class MessageCard(QFrame):
    def __init__(self, role: str, name: str, text: str, stamp: str, parent=None):
        super().__init__(parent)
        self.setObjectName("MessageCard")
        accent_map = {
            "user": (C.BORDER_B, C.WHITE),
            "assistant": (C.PRI, C.PRI),
            "system": ("#4b8cff", "#4b8cff"),
            "file": ("#35c96d", "#35c96d"),
            "error": ("#ff8b3d", "#ff8b3d"),
        }
        border_col, left_col = accent_map.get(role, accent_map["system"])
        self.setStyleSheet(
            f"""
            QFrame#MessageCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(13, 15, 20, 246),
                    stop:1 rgba(5, 6, 9, 238));
                border: 1px solid {border_col};
                border-left: 3px solid {left_col};
                border-radius: 12px;
            }}
            """
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(12)

        avatar = QLabel(name[:1].upper())
        avatar.setFixedSize(34, 34)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))

        palette = {
            "user": ("#0d0f14", C.WHITE, C.BORDER_B),
            "assistant": ("#12090a", C.RED, C.PRI),
            "system": ("#101525", "#7cb7ff", "#4b8cff"),
            "file": ("#0f1410", C.GREEN, "#35c96d"),
            "error": ("#1a0f10", "#ffb074", "#ff8b3d"),
        }
        bg, fg, border = palette.get(role, palette["system"])
        avatar.setStyleSheet(
            f"background: {bg}; color: {fg}; border: 1px solid {border}; border-radius: 20px;"
        )

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(3)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)

        name_lbl = QLabel(name)
        name_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        name_lbl.setStyleSheet(f"color: {C.WHITE}; background: transparent;")

        time_lbl = QLabel(stamp)
        time_lbl.setFont(QFont("Segoe UI", 7))
        time_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        time_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        top.addWidget(name_lbl)
        top.addStretch()
        top.addWidget(time_lbl)

        text_lbl = QLabel(text)
        text_lbl.setWordWrap(True)
        text_lbl.setFont(QFont("Segoe UI", 9))
        text_color = {
            "user": C.TEXT,
            "assistant": C.WHITE,
            "system": C.TEXT_MED,
            "file": C.GREEN,
            "error": C.RED,
        }.get(role, C.TEXT)
        text_lbl.setStyleSheet(f"color: {text_color}; background: transparent;")

        body.addLayout(top)
        body.addWidget(text_lbl)
        lay.addWidget(avatar)
        lay.addLayout(body)


class TaskCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TaskCard")
        self._active = False
        self._workspace_locked = False
        self.setStyleSheet(
            f"""
            QFrame#TaskCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(16, 18, 24, 230),
                    stop:0.6 rgba(10, 12, 18, 210),
                    stop:1 rgba(5, 7, 11, 200));
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 16px;
            }}
            QFrame#TaskCard:hover {{
                border: 1px solid rgba(255, 69, 69, 0.28);
            }}
            """
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        row = QHBoxLayout()
        self._title = QLabel("Task Workspace")
        self._title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._title.setStyleSheet(f"color: {C.RED}; background: transparent;")

        self._pct = QLabel("0%")
        self._pct.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._pct.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        self._pct.setAlignment(Qt.AlignmentFlag.AlignRight)
        row.addWidget(self._title)
        row.addStretch()
        row.addWidget(self._pct)
        lay.addLayout(row)

        self._command_lbl = QLabel("Command: waiting for input")
        self._command_lbl.setWordWrap(True)
        self._command_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._command_lbl.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        lay.addWidget(self._command_lbl)

        self._plan_lbl = QLabel("Plan: Brahma will generate a task plan after you send a command.")
        self._plan_lbl.setWordWrap(True)
        self._plan_lbl.setFont(QFont("Segoe UI", 9))
        self._plan_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        lay.addWidget(self._plan_lbl)

        self._status_lbl = QLabel("Status: Idle")
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._status_lbl.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        lay.addWidget(self._status_lbl)

        self._output_lbl = QLabel("Output: Ready to work.")
        self._output_lbl.setWordWrap(True)
        self._output_lbl.setFont(QFont("Segoe UI", 9))
        self._output_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        lay.addWidget(self._output_lbl)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(8)
        self._bar.setStyleSheet(
            f"""
            QProgressBar {{
                background: rgba(255,255,255,0.06);
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background: {C.RED};
                border-radius: 3px;
            }}
            """
        )
        lay.addWidget(self._bar)

        self._foot = QLabel("Working on it...")
        self._foot.setFont(QFont("Segoe UI", 9))
        self._foot.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        lay.addWidget(self._foot)

    def set_task(self, title: str, desc: str, percent: int):
        if self._workspace_locked:
            return
        if self._active:
            self.update_workspace(title=title, status=desc, percent=percent)
            return
        self._title.setText(title)
        self._status_lbl.setText(desc)
        self._output_lbl.setText(desc)
        self._plan_lbl.setText("Plan: Brahma will generate a task plan after you send a command.")
        self._command_lbl.setText("Command: waiting for input")
        self._pct.setText(f"{percent}%")
        self._bar.setValue(max(0, min(100, percent)))

    def _format_plan(self, plan: list[str] | str | None) -> str:
        if not plan:
            return "Plan: • Understand the request\n       • Execute the right tools\n       • Return the result"
        if isinstance(plan, str):
            text = plan.strip()
            return f"Plan: {text}" if text.lower().startswith("plan:") else f"Plan: {text}"
        items = [str(item).strip() for item in plan if str(item).strip()]
        if not items:
            return "Plan: • Understand the request\n       • Execute the right tools\n       • Return the result"
        return "Plan:\n" + "\n".join(f"• {item}" for item in items)

    def start_workspace(self, command: str, plan: list[str] | str | None = None, source: str = "local"):
        self._active = True
        self._workspace_locked = False
        self._title.setText("Task Workspace")
        self._command_lbl.setText(f"Command: {command or 'waiting for input'}")
        self._plan_lbl.setText(self._format_plan(plan))
        self._status_lbl.setText("Status: Planning task...")
        self._output_lbl.setText("Output: Waiting for execution.")
        self._pct.setText("8%")
        self._bar.setValue(8)
        self._foot.setText(f"Source: {source}")
        self.show()

    def update_workspace(self, *, title: str | None = None, command: str | None = None, plan: list[str] | str | None = None,
                         status: str | None = None, output: str | None = None, percent: int | None = None,
                         footer: str | None = None):
        if title:
            self._title.setText(title)
        if command:
            self._command_lbl.setText(f"Command: {command}")
        if plan is not None:
            self._plan_lbl.setText(self._format_plan(plan))
        if status:
            self._status_lbl.setText(f"Status: {status}" if not status.lower().startswith("status:") else status)
        if output:
            self._output_lbl.setText(f"Output: {output}" if not output.lower().startswith("output:") else output)
        if percent is not None:
            pct = max(0, min(100, int(percent)))
            self._pct.setText(f"{pct}%")
            self._bar.setValue(pct)
        if footer:
            self._foot.setText(footer)
        self._active = True
        self._workspace_locked = False
        self.show()

    def finish_workspace(self, result: str, status: str = "Task completed.", percent: int = 100):
        self._active = False
        self._workspace_locked = True
        self._title.setText("Task Complete")
        self._status_lbl.setText(f"Status: {status}")
        self._output_lbl.setText(f"Output: {result or 'Done.'}")
        self._pct.setText(f"{max(0, min(100, percent))}%")
        self._bar.setValue(max(0, min(100, percent)))
        self._foot.setText("Resetting workspace shortly...")
        self.show()
        QTimer.singleShot(5000, self.clear_workspace)

    def clear_workspace(self):
        self._active = False
        self._workspace_locked = False
        self._title.setText("Ready")
        self._command_lbl.setText("Command: waiting for input")
        self._plan_lbl.setText("Plan: Brahma will generate a task plan after you send a command.")
        self._status_lbl.setText("Status: Idle")
        self._output_lbl.setText("Output: Ready to work.")
        self._pct.setText("0%")
        self._bar.setValue(0)
        self._foot.setText("Working on it...")
        self.hide()


def _fmt_time_stamp(value: int | float | None = None) -> str:
    try:
        from datetime import datetime
        if value is None:
            dt = datetime.now()
        else:
            stamp = float(value)
            if stamp > 10_000_000_000:
                stamp /= 1000.0
            dt = datetime.fromtimestamp(stamp)
        return dt.strftime("%H:%M")
    except Exception:
        return ""


def _markdown_to_html(text: str, role: str = "assistant") -> str:
    safe = html_lib.escape(text or "")
    safe = safe.replace("\r\n", "\n").replace("\r", "\n")

    def _code_block(match):
        code = html_lib.escape(match.group(1).rstrip("\n"))
        return (
            '<pre style="margin:10px 0; padding:10px 12px; border-radius:10px; '
            'background:rgba(0,0,0,0.35); color:#f4f6f8; border:1px solid rgba(255,255,255,0.10);">'
            f'<code>{code}</code></pre>'
        )

    safe = re.sub(r"```(?:[\w+-]+\n)?(.*?)```", _code_block, safe, flags=re.S)
    safe = re.sub(
        r"`([^`]+)`",
        r'<code style="padding:1px 5px; border-radius:5px; background:rgba(255,255,255,0.08); color:#fff;">\1</code>',
        safe,
    )
    safe = re.sub(r"(?m)^### (.+)$", r'<h3 style="margin:10px 0 6px 0; font-size:13px;">\1</h3>', safe)
    safe = re.sub(r"(?m)^## (.+)$", r'<h2 style="margin:10px 0 8px 0; font-size:15px;">\1</h2>', safe)
    safe = re.sub(r"(?m)^# (.+)$", r'<h1 style="margin:10px 0 8px 0; font-size:17px;">\1</h1>', safe)
    safe = safe.replace("\n", "<br>")
    accent = C.WHITE if role == "assistant" else C.TEXT
    return (
        f'<div style="color:{accent}; font-size:12px; line-height:1.45; white-space:normal;">'
        f"{safe}"
        "</div>"
    )


class AttachmentCard(QFrame):
    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("AttachmentCard")
        self.setStyleSheet("""
            QFrame#AttachmentCard {
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,69,69,0.26);
                border-radius: 10px;
            }
        """)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(10)
        icon = QLabel("⎙")
        icon.setFixedSize(26, 26)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("color: #ff7777; background: rgba(255,255,255,0.03); border-radius: 13px; font-size: 14px;")
        lay.addWidget(icon)
        txt = QVBoxLayout()
        txt.setContentsMargins(0, 0, 0, 0)
        txt.setSpacing(2)
        t = QLabel(title)
        t.setStyleSheet("color: #ffffff; background: transparent; font: 600 9pt 'Segoe UI';")
        s = QLabel(subtitle)
        s.setStyleSheet("color: rgba(255,255,255,0.62); background: transparent; font: 8pt 'Segoe UI';")
        txt.addWidget(t)
        txt.addWidget(s)
        lay.addLayout(txt, 1)


class EventCard(QFrame):
    def __init__(self, title: str, detail: str, stamp: str, icon: str = "●", accent: str = "#ff4545", parent=None):
        super().__init__(parent)
        self.setObjectName("EventCard")
        self.setStyleSheet(
            f"""
            QFrame#EventCard {{
                background: rgba(12, 13, 17, 220);
                border: 1px solid rgba(255,69,69,0.18);
                border-left: 3px solid {accent};
                border-radius: 12px;
            }}
            """
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(10)

        icon_lbl = QLabel(icon[:1])
        icon_lbl.setFixedSize(30, 30)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        icon_lbl.setStyleSheet(
            f"background: rgba(255,69,69,0.08); color: {accent}; border: 1px solid rgba(255,69,69,0.22); border-radius: 15px;"
        )
        lay.addWidget(icon_lbl)

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(3)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)
        title_lbl = QLabel(title)
        title_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #ffffff; background: transparent;")
        stamp_lbl = QLabel(stamp)
        stamp_lbl.setFont(QFont("Segoe UI", 7))
        stamp_lbl.setStyleSheet("color: rgba(255,255,255,0.55); background: transparent;")
        top.addWidget(title_lbl)
        top.addStretch(1)
        top.addWidget(stamp_lbl)
        body.addLayout(top)

        detail_lbl = QLabel(detail)
        detail_lbl.setWordWrap(True)
        detail_lbl.setFont(QFont("Segoe UI", 9))
        detail_lbl.setStyleSheet("color: rgba(255,255,255,0.78); background: transparent;")
        body.addWidget(detail_lbl)
        lay.addLayout(body, 1)


class ArtifactCard(QFrame):
    def __init__(self, title: str, file_type: str = "File", status: str = "Generated", path: str = "", parent=None):
        super().__init__(parent)
        self._path = path.strip()
        self.setObjectName("ArtifactCard")
        self.setStyleSheet(
            """
            QFrame#ArtifactCard {
                background: rgba(11, 12, 16, 230);
                border: 1px solid rgba(255,69,69,0.22);
                border-radius: 12px;
            }
            QPushButton {
                background: rgba(255,255,255,0.04);
                color: #ffffff;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 8px;
                padding: 6px 10px;
            }
            QPushButton:hover {
                background: rgba(255,69,69,0.08);
                border: 1px solid rgba(255,69,69,0.35);
            }
            QPushButton:disabled {
                color: rgba(255,255,255,0.35);
            }
            """
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(10)
        badge = QLabel("↗")
        badge.setFixedSize(30, 30)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        badge.setStyleSheet("background: rgba(255,69,69,0.08); color: #ff7777; border: 1px solid rgba(255,69,69,0.24); border-radius: 15px;")
        head.addWidget(badge)

        meta = QVBoxLayout()
        meta.setContentsMargins(0, 0, 0, 0)
        meta.setSpacing(2)
        name_lbl = QLabel(title or "Generated file")
        name_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        name_lbl.setStyleSheet("color: #ffffff; background: transparent;")
        type_lbl = QLabel(f"{file_type} • {status}")
        type_lbl.setFont(QFont("Segoe UI", 8))
        type_lbl.setStyleSheet("color: rgba(255,255,255,0.62); background: transparent;")
        meta.addWidget(name_lbl)
        meta.addWidget(type_lbl)
        head.addLayout(meta, 1)
        lay.addLayout(head)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._open_btn = QPushButton("Open")
        self._reveal_btn = QPushButton("Reveal Folder")
        self._open_btn.clicked.connect(self._open_file)
        self._reveal_btn.clicked.connect(self._reveal_file)
        if not self._path or not Path(self._path).exists():
            self._open_btn.setEnabled(False)
            self._reveal_btn.setEnabled(False)
        btn_row.addWidget(self._open_btn)
        btn_row.addWidget(self._reveal_btn)
        btn_row.addStretch(1)
        lay.addLayout(btn_row)

    def _open_file(self):
        if not self._path or not Path(self._path).exists():
            return
        try:
            os.startfile(self._path)
        except Exception:
            pass

    def _reveal_file(self):
        if not self._path or not Path(self._path).exists():
            return
        try:
            if platform.system() == "Windows":
                subprocess.Popen(["explorer", "/select,", self._path])
            else:
                os.startfile(str(Path(self._path).parent))
        except Exception:
            pass


class ChatBubble(QFrame):
    def __init__(self, role: str, name: str, text: str, stamp: str, attachments: list[dict] | None = None, parent=None, animate: bool = False):
        super().__init__(parent)
        self._role = role
        self._full_text = text or ""
        self._typing_index = 0
        self._typing_timer: QTimer | None = None
        self.setObjectName("ChatBubble")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setStyleSheet(
            """
            QFrame#ChatBubble {
                background: rgba(10, 11, 14, 220);
                border: 1px solid rgba(255,69,69,0.12);
                border-left: 2px solid rgba(255,69,69,0.65);
                border-radius: 12px;
            }
            """
        )
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        row = QHBoxLayout()
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(8)

        avatar = QLabel((name or role[:1]).strip()[:1].upper())
        avatar.setFixedSize(28, 28)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        avatar_bg = {
            "user": ("#0f1015", "#ffffff", "rgba(255,255,255,0.18)"),
            "assistant": ("#12090a", "#ff7777", "rgba(255,69,69,0.35)"),
            "system": ("#0f1015", "#ff7777", "rgba(255,69,69,0.25)"),
            "file": ("#0c120f", "#37ff5f", "rgba(55,255,95,0.35)"),
        }.get(role, ("#0f1015", "#ffffff", "rgba(255,255,255,0.18)"))
        avatar.setStyleSheet(
            f"background: {avatar_bg[0]}; color: {avatar_bg[1]}; border: 1px solid {avatar_bg[2]}; border-radius: 17px;"
        )

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(4)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)
        name_lbl = QLabel(name)
        name_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        name_lbl.setStyleSheet("color: #ffffff; background: transparent;")
        time_lbl = QLabel(stamp)
        time_lbl.setFont(QFont("Segoe UI", 7))
        time_lbl.setStyleSheet("color: rgba(255,255,255,0.55); background: transparent;")
        top.addWidget(name_lbl)
        top.addStretch()
        top.addWidget(time_lbl)

        self._browser = QTextBrowser()
        self._browser.setFrameShape(QFrame.Shape.NoFrame)
        self._browser.setOpenExternalLinks(True)
        self._browser.setReadOnly(True)
        self._browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._browser.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._browser.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self._browser.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self._browser.setStyleSheet(
            """
            QTextBrowser {
                background: transparent;
                border: none;
                color: #f4f6f8;
                padding: 0;
            }
            """
        )
        self._browser.document().setDocumentMargin(0)
        self._render_text(text or "")

        body.addLayout(top)
        body.addWidget(self._browser, 1)

        if attachments:
            for attachment in attachments:
                title = str(attachment.get("name") or attachment.get("title") or attachment.get("path") or "Attachment")
                subtitle = str(attachment.get("path") or attachment.get("description") or "")
                body.addWidget(ArtifactCard(title, file_type=Path(title).suffix.lstrip(".").upper() or "File", status="Attached", path=subtitle or title))

        if role == "user":
            row.addStretch(1)
            row.addLayout(body, 0)
            row.addWidget(avatar)
        else:
            row.addWidget(avatar)
            row.addLayout(body, 1)
            row.addStretch(1)
        outer.addLayout(row)
        if animate and role == "assistant":
            self._start_typing_animation()
        else:
            QTimer.singleShot(0, self._fit_to_content)

    def _render_text(self, text: str, final: bool = True):
        if final:
            try:
                self._browser.setMarkdown(text or "")
                return
            except Exception:
                pass
        self._browser.setHtml(_markdown_to_html(text or "", self._role))

    def _start_typing_animation(self):
        self._typing_timer = QTimer(self)
        self._typing_timer.setInterval(14)
        self._typing_timer.timeout.connect(self._tick_typing)
        self._typing_timer.start()

    def _tick_typing(self):
        self._typing_index = min(len(self._full_text), self._typing_index + 3)
        snippet = self._full_text[:self._typing_index]
        self._render_text(snippet, final=False)
        if self._typing_index >= len(self._full_text):
            try:
                self._typing_timer.stop()
            except Exception:
                pass
            self._render_text(self._full_text, final=True)
            QTimer.singleShot(0, self._fit_to_content)

    def _fit_to_content(self):
        try:
            doc = self._browser.document()
            viewport = self.parentWidget()
            while viewport is not None and not hasattr(viewport, "viewport"):
                viewport = viewport.parentWidget()
            viewport_width = viewport.viewport().width() if viewport and hasattr(viewport, "viewport") else self.width()
            role_width = {
                "user": 0.62,
                "assistant": 0.78,
                "system": 0.72,
                "file": 0.80,
            }.get((getattr(self, "_role", "") or "").lower(), 0.76)
            width = max(260, min(int(viewport_width * role_width), max(280, viewport_width - 110)))
            doc.setTextWidth(width)
            doc.adjustSize()
            height = int(doc.size().height()) + 8
            self._browser.setFixedWidth(width)
            self._browser.setMinimumHeight(height)
            self._browser.setMaximumHeight(max(height, 24))
            self._browser.updateGeometry()
            self.updateGeometry()
        except Exception:
            pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_to_content()


class HistoryConversationItem(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, conversation_id: str, title: str, stamp: str, pinned: bool = False, parent=None):
        super().__init__(parent)
        self._conversation_id = conversation_id
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("HistoryConversationItem")
        self.setStyleSheet(
            """
            QFrame#HistoryConversationItem {
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,69,69,0.18);
                border-radius: 10px;
            }
            QFrame#HistoryConversationItem:hover {
                background: rgba(255,69,69,0.07);
                border: 1px solid rgba(255,69,69,0.32);
            }
            """
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(10)

        icon = QLabel("B")
        icon.setFixedSize(30, 30)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("background: rgba(255,69,69,0.10); color: #ff7777; border: 1px solid rgba(255,69,69,0.28); border-radius: 15px; font: 700 11pt 'Segoe UI';")
        lay.addWidget(icon)

        meta = QVBoxLayout()
        meta.setContentsMargins(0, 0, 0, 0)
        meta.setSpacing(2)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        title_lbl = QLabel(title or "Conversation")
        title_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #ffffff; background: transparent;")
        row.addWidget(title_lbl)
        if pinned:
            pin = QLabel("PIN")
            pin.setStyleSheet("color: #37ff5f; background: transparent; font: 700 7pt 'Courier New';")
            row.addWidget(pin)
        row.addStretch()
        stamp_lbl = QLabel(stamp)
        stamp_lbl.setFont(QFont("Segoe UI", 7))
        stamp_lbl.setStyleSheet("color: rgba(255,255,255,0.50); background: transparent;")
        row.addWidget(stamp_lbl)
        meta.addLayout(row)
        lay.addLayout(meta, 1)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._conversation_id)


class ConversationFeed(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(
            """
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: transparent;
                width: 8px;
                border: none;
                margin: 6px 0 6px 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,69,69,0.45);
                border-radius: 4px;
                min-height: 24px;
            }
            """
        )
        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(2, 2, 2, 2)
        self._layout.setSpacing(8)
        self._layout.addStretch(1)
        self.setWidget(self._content)
        self._empty_widget: QWidget | None = None
        self._message_count = 0

    def _ensure_empty_widget(self):
        if self._empty_widget is not None:
            return self._empty_widget
        frame = QFrame()
        frame.setStyleSheet(
            """
            QFrame {
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,69,69,0.16);
                border-radius: 14px;
            }
            QPushButton {
                background: rgba(255,255,255,0.04);
                color: #ffffff;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                padding: 8px 12px;
                text-align: left;
            }
            QPushButton:hover {
                background: rgba(255,69,69,0.08);
                border: 1px solid rgba(255,69,69,0.28);
            }
            """
        )
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)
        title = QLabel("Try asking Brahma")
        title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff; background: transparent;")
        subtitle = QLabel("Create a presentation, analyze a screen, build a website, organize files, or run browser automation.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: rgba(255,255,255,0.64); background: transparent;")
        lay.addWidget(title)
        lay.addWidget(subtitle)
        grid = QGridLayout()
        grid.setSpacing(8)
        self._empty_widget_buttons = []
        for idx, suggestion in enumerate([
            "Create Presentation",
            "Analyze Screen",
            "Build Website",
            "Organize Downloads",
            "Browser Automation",
        ]):
            btn = QPushButton(suggestion)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, s=suggestion: self._emit_empty_suggestion(s))
            self._empty_widget_buttons.append(btn)
            grid.addWidget(btn, idx // 2, idx % 2)
        lay.addLayout(grid)
        self._empty_widget = frame
        return frame

    def _emit_empty_suggestion(self, text: str):
        root = self.parentWidget()
        while root is not None and not hasattr(root, "command_submitted"):
            root = root.parentWidget()
        if root is not None and hasattr(root, "command_submitted"):
            root.command_submitted.emit(text)

    def clear_messages(self):
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None and widget is not self._empty_widget:
                widget.deleteLater()
        if self._empty_widget is not None:
            self._empty_widget.hide()
        self._layout.addStretch(1)
        self._message_count = 0

    def add_message(self, role: str, name: str, text: str, stamp: str, attachments: list[dict] | None = None, animate: bool = False, event_type: str | None = None):
        if self._layout.count() and self._layout.itemAt(self._layout.count() - 1).spacerItem() is not None:
            self._layout.takeAt(self._layout.count() - 1)
        role = (role or "").strip().lower()
        if role == "system":
            bubble = self._build_event_card(text, stamp, event_type=event_type)
        elif role == "file":
            bubble = self._build_artifact_card(text, attachments=attachments, stamp=stamp)
        else:
            bubble = ChatBubble(role, name, text, stamp, attachments=attachments, parent=self, animate=animate)
        self._layout.addWidget(bubble)
        self._layout.addStretch(1)
        self._message_count += 1
        self._sync_empty_state()
        QTimer.singleShot(0, self.scroll_to_bottom)

    def _build_event_card(self, text: str, stamp: str, event_type: str | None = None) -> QWidget:
        low = (event_type or text or "").lower()
        title = "System Event"
        icon = "●"
        accent = "#ff4545"
        if "discord" in low and "connected" in low:
            title, icon, accent = "Discord Connected", "◉", "#5865F2"
        elif "presentation" in low:
            title, icon, accent = "Presentation Generated", "▣", "#ff7a45"
        elif "website" in low:
            title, icon, accent = "Website Created", "⌂", "#37ff5f"
        elif "spreadsheet" in low:
            title, icon, accent = "Spreadsheet Generated", "▦", "#6fd6ff"
        elif "browser" in low:
            title, icon, accent = "Browser Automation Completed", "↗", "#ffbf00"
        elif "organ" in low and "file" in low:
            title, icon, accent = "File Organization Completed", "🗂", "#37ff5f"
        elif "screen" in low and "analysis" in low:
            title, icon, accent = "Screen Analysis Completed", "◫", "#6fd6ff"
        return EventCard(title, text, stamp, icon=icon, accent=accent, parent=self)

    def _build_artifact_card(self, text: str, attachments: list[dict] | None = None, stamp: str = "") -> QWidget:
        attachment = (attachments or [{}])[0] if attachments else {}
        path = str(attachment.get("path") or attachment.get("file") or attachment.get("name") or "").strip()
        title = str(attachment.get("name") or attachment.get("title") or Path(path).name or "Generated File").strip()
        suffix = Path(path or title).suffix.lstrip(".").upper() or (str(attachment.get("type") or "FILE")).upper()
        status = "Ready"
        return ArtifactCard(title, file_type=suffix, status=status, path=path or title, parent=self)

    def scroll_to_bottom(self):
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())

    def load_messages(self, messages: list[dict[str, Any]]):
        self.clear_messages()
        for msg in messages:
            role = (msg.get("role") or "assistant").strip().lower()
            content = msg.get("content") or ""
            stamp = _fmt_time_stamp(msg.get("timestamp"))
            attachments = msg.get("attachments") or []
            name = {
                "user": "You",
                "assistant": "Brahma",
                "system": "System",
                "file": "Files",
            }.get(role, "Brahma")
            self.add_message(role, name, content, stamp, attachments=attachments, animate=False)
        self._sync_empty_state()
        QTimer.singleShot(0, self.scroll_to_bottom)

    def _sync_empty_state(self):
        if self._empty_widget is None:
            self._ensure_empty_widget()
        if self._message_count <= 0:
            if self._layout.indexOf(self._empty_widget) == -1:
                self._layout.insertWidget(0, self._empty_widget)
            self._empty_widget.show()
        else:
            if self._layout.indexOf(self._empty_widget) != -1:
                self._layout.removeWidget(self._empty_widget)
            self._empty_widget.hide()

    def has_messages(self) -> bool:
        return self._message_count > 0

    def resizeEvent(self, event):
        super().resizeEvent(event)
        for i in range(self._layout.count()):
            widget = self._layout.itemAt(i).widget()
            if hasattr(widget, "_fit_to_content"):
                widget._fit_to_content()
        QTimer.singleShot(0, self.scroll_to_bottom)


class TaskDock(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TaskDock")
        self._collapsed = False
        self._expanded_w = 392
        self._collapsed_w = 44
        self.setFixedWidth(self._expanded_w)
        self.setStyleSheet(
            f"""
            QFrame#TaskDock {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(7, 8, 12, 250),
                    stop:1 rgba(3, 4, 6, 245));
                border-left: 1px solid rgba(255, 69, 69, 0.55);
            }}
            """
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 10, 8, 10)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(8)
        self._title = QLabel("TASK WORKSPACE")
        self._title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self._title.setStyleSheet(f"color: {C.PRI}; background: transparent; letter-spacing: 1px;")
        header.addWidget(self._title)
        header.addStretch()

        self._toggle_btn = QPushButton(">")
        self._toggle_btn.setFixedSize(34, 34)
        self._toggle_btn.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(12,14,18,245); color: {C.WHITE}; border: 1px solid {C.BORDER_B}; border-radius: 8px; }}"
            f"QPushButton:hover {{ color: {C.PRI}; border: 1px solid {C.PRI}; }}"
        )
        self._toggle_btn.clicked.connect(self.toggle_collapsed)
        header.addWidget(self._toggle_btn)
        root.addLayout(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.PRI_GHO}; margin: 2px 0;")
        root.addWidget(sep)

        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(self._content)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self._task_card = TaskCard()
        lay.addWidget(self._task_card)

        self._mini_hint = QLabel("TASK")
        self._mini_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._mini_hint.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._mini_hint.setStyleSheet(
            f"color: {C.PRI}; background: rgba(12,14,18,245); border: 1px solid {C.BORDER_B}; border-radius: 8px; padding: 10px 4px;"
        )
        self._mini_hint.setVisible(False)
        lay.addWidget(self._mini_hint)

        root.addWidget(self._content, stretch=1)
        self._apply_state()

    def toggle_collapsed(self):
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool):
        self._collapsed = bool(collapsed)
        self._apply_state()

    def is_collapsed(self) -> bool:
        return self._collapsed

    def _apply_state(self):
        self._content.setVisible(not self._collapsed)
        self._mini_hint.setVisible(self._collapsed)
        self._toggle_btn.setText(">" if self._collapsed else "<")
        self._toggle_btn.setToolTip("Open task workspace" if self._collapsed else "Collapse task workspace")
        self._title.setVisible(not self._collapsed)
        self.setFixedWidth(self._collapsed_w if self._collapsed else self._expanded_w)

    def start_workspace(self, command: str, plan: list[str] | str | None = None, source: str = "local"):
        self._task_card.start_workspace(command, plan, source)
        if self._collapsed:
            return

    def update_workspace(self, **kwargs):
        self._task_card.update_workspace(**kwargs)

    def finish_workspace(self, result: str, status: str = "Task completed.", percent: int = 100):
        self._task_card.finish_workspace(result, status, percent)

    def clear_workspace(self):
        self._task_card.clear_workspace()


class WorkspaceSidebar(QWidget):
    command_submitted = pyqtSignal(str)
    close_requested = pyqtSignal()
    attach_requested = pyqtSignal()
    mic_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._collapsed = True
        self._expanded_w = 468
        self._target_h = 860
        self._active_conversation_id: str | None = None
        self._store = workspace_store()
        self._anim = QPropertyAnimation(self, b"geometry", self)
        self._anim.setDuration(300)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._panel = QFrame(self)
        self._panel.setObjectName("WorkspaceSidebarPanel")
        self._panel.setStyleSheet(
            """
            QFrame#WorkspaceSidebarPanel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(16, 18, 24, 230),
                    stop:0.55 rgba(10, 12, 18, 210),
                    stop:1 rgba(5, 7, 11, 200));
                border: 1px solid rgba(255, 255, 255, 0.14);
                border-radius: 22px;
                box-shadow: 0 12px 35px rgba(0,0,0,0.28);
            }
            """
        )
        root = QHBoxLayout(self._panel)
        root.setContentsMargins(14, 14, 12, 14)
        root.setSpacing(10)

        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        content = QVBoxLayout(self._content)
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(10)
        self._title = QLabel("CHAT + TASK WORKSPACE")
        self._title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._title.setStyleSheet("color: #FFFFFF; background: transparent; letter-spacing: 1px;")
        header.addWidget(self._title)
        header.addStretch()
        self._close_btn = QPushButton("BRAHMA")
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setFixedHeight(30)
        self._close_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._close_btn.setStyleSheet(
            """
            QPushButton {
                background: rgba(15,15,20,220);
                color: #FFFFFF;
                border: 1px solid rgba(255,69,69,120);
                border-radius: 10px;
                padding: 0 12px;
            }
            QPushButton:hover {
                border: 1px solid rgba(255,69,69,200);
            }
            """
        )
        self._close_btn.clicked.connect(self.close_requested.emit)
        header.addWidget(self._close_btn)
        content.addLayout(header)

        self._tab_row = QHBoxLayout()
        self._tab_row.setSpacing(8)
        self._chat_tab_btn = self._make_tab_button("CHAT", True)
        self._history_tab_btn = self._make_tab_button("HISTORY", False)
        self._chat_tab_btn.clicked.connect(lambda: self._set_tab(0))
        self._history_tab_btn.clicked.connect(lambda: self._set_tab(1))
        self._tab_row.addWidget(self._chat_tab_btn)
        self._tab_row.addWidget(self._history_tab_btn)
        self._tab_row.addStretch(1)
        content.addLayout(self._tab_row)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_chat_tab())
        self._stack.addWidget(self._build_history_tab())
        content.addWidget(self._stack, 1)

        root.addWidget(self._content, stretch=1)

        self._panel.hide()
        self.hide()
        self._set_tab(0)
        self._ensure_active_conversation()
        self._load_active_conversation()
        self._refresh_history()
        self._apply_state()

    def _make_tab_button(self, text: str, active: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(34)
        btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        btn.setCheckable(True)
        btn.setChecked(active)
        btn.setStyleSheet(self._tab_style(active))
        return btn

    def _tab_style(self, active: bool) -> str:
        if active:
            return """
                QPushButton {
                    background: rgba(255,69,69,0.16);
                    color: #FFFFFF;
                    border: 1px solid rgba(255,69,69,180);
                    border-radius: 10px;
                    padding: 0 14px;
                }
            """
        return """
            QPushButton {
                background: rgba(255,255,255,0.04);
                color: rgba(255,255,255,0.82);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
                padding: 0 14px;
            }
            QPushButton:hover {
                background: rgba(255,69,69,0.08);
                border: 1px solid rgba(255,69,69,120);
            }
        """

    def _set_tab(self, index: int):
        index = 0 if index == 0 else 1
        self._stack.setCurrentIndex(index)
        self._chat_tab_btn.setStyleSheet(self._tab_style(index == 0))
        self._history_tab_btn.setStyleSheet(self._tab_style(index == 1))
        self._chat_tab_btn.setChecked(index == 0)
        self._history_tab_btn.setChecked(index == 1)
        if index == 1:
            self._history_search.setFocus(Qt.FocusReason.TabFocusReason)

    def _build_chat_tab(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self._task_card = TaskCard()
        lay.addWidget(self._task_card)

        self._memory_frame = QFrame()
        self._memory_frame.setVisible(False)
        self._memory_frame.setStyleSheet(
            """
            QFrame {
                background: rgba(255,69,69,0.05);
                border: 1px solid rgba(255,69,69,0.24);
                border-radius: 12px;
            }
            """
        )
        mem_lay = QVBoxLayout(self._memory_frame)
        mem_lay.setContentsMargins(12, 10, 12, 10)
        mem_lay.setSpacing(6)
        mem_title = QLabel("Using Memory:")
        mem_title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        mem_title.setStyleSheet("color: #FFFFFF; background: transparent;")
        self._memory_items = QLabel("")
        self._memory_items.setWordWrap(True)
        self._memory_items.setStyleSheet("color: rgba(255,255,255,0.75); background: transparent;")
        mem_lay.addWidget(mem_title)
        mem_lay.addWidget(self._memory_items)
        lay.addWidget(self._memory_frame)

        self._feed = ConversationFeed()
        lay.addWidget(self._feed, 1)

        # Keep an internal input stub for signal safety, but do not render a command bar here.
        self._input = QLineEdit(self)
        self._input.hide()

        return page

    def _build_history_tab(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self._history_search = QLineEdit()
        self._history_search.setPlaceholderText("Search conversations...")
        self._history_search.setFont(QFont("Segoe UI", 10))
        self._history_search.setFixedHeight(38)
        self._history_search.setStyleSheet(
            """
            QLineEdit {
                background: rgba(10,11,14,205);
                color: #FFFFFF;
                border: 1px solid rgba(255,69,69,100);
                border-radius: 12px;
                padding: 0 12px;
            }
            QLineEdit:focus {
                border: 1px solid rgba(255,69,69,190);
            }
            """
        )
        self._history_search.textChanged.connect(self._refresh_history)
        lay.addWidget(self._history_search)

        self._history_scroll = QScrollArea()
        self._history_scroll.setWidgetResizable(True)
        self._history_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._history_scroll.setStyleSheet(
            """
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: transparent;
                width: 8px;
                border: none;
                margin: 6px 0 6px 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,69,69,0.45);
                border-radius: 4px;
                min-height: 24px;
            }
            """
        )
        self._history_content = QWidget()
        self._history_content.setStyleSheet("background: transparent;")
        self._history_layout = QVBoxLayout(self._history_content)
        self._history_layout.setContentsMargins(0, 0, 0, 0)
        self._history_layout.setSpacing(10)
        self._history_layout.addStretch(1)
        self._history_scroll.setWidget(self._history_content)
        lay.addWidget(self._history_scroll, 1)
        return page

    def _ensure_active_conversation(self, first_message: str | None = None) -> str:
        convo_id = self._active_conversation_id
        if convo_id:
            convo = self._store.get_conversation(convo_id)
            if convo:
                return convo_id
        convo_id = self._store.ensure_active_conversation(first_message or "")
        self._active_conversation_id = convo_id
        return convo_id

    def _group_label(self, title: str) -> QLabel:
        lbl = QLabel(title.upper())
        lbl.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        lbl.setStyleSheet("color: rgba(255,255,255,0.58); background: transparent; letter-spacing: 1px;")
        return lbl

    def _clear_layout(self, layout: QVBoxLayout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _refresh_history(self, *_):
        search = self._history_search.text().strip() if hasattr(self, "_history_search") else ""
        self._clear_layout(self._history_layout)
        groups = self._store.grouped_conversations(search)
        current = self._active_conversation_id
        if not groups:
            empty = QLabel("No conversations yet.")
            empty.setStyleSheet("color: rgba(255,255,255,0.60); background: transparent;")
            self._history_layout.addWidget(empty)
            self._history_layout.addStretch(1)
            return
        for group_name, items in groups.items():
            self._history_layout.addWidget(self._group_label(group_name))
            for item in items:
                widget = HistoryConversationItem(
                    item["id"],
                    item["title"],
                    _fmt_time_stamp(item["updatedAt"]),
                    pinned=bool(item["pinned"]),
                )
                if item["id"] == current:
                    widget.setStyleSheet(
                        """
                        QFrame#HistoryConversationItem {
                            background: rgba(255,69,69,0.10);
                            border: 1px solid rgba(255,69,69,0.55);
                            border-radius: 10px;
                        }
                        QFrame#HistoryConversationItem:hover {
                            background: rgba(255,69,69,0.14);
                            border: 1px solid rgba(255,69,69,0.70);
                        }
                        """
                    )
                widget.clicked.connect(self._load_conversation)
                self._history_layout.addWidget(widget)
            self._history_layout.addSpacing(4)
        self._history_layout.addStretch(1)

    def _show_memory_banner(self, memories: list[dict[str, object]]):
        texts = [str(m.get("content") or "").strip() for m in memories if str(m.get("content") or "").strip()]
        if not texts:
            self._memory_items.setText("")
            self._memory_frame.hide()
            return
        self._memory_items.setText("• " + "\n• ".join(texts[:4]))
        self._memory_frame.show()

    def _hide_memory_banner(self):
        self._memory_items.setText("")
        self._memory_frame.hide()

    def _load_active_conversation(self):
        convo_id = self._ensure_active_conversation()
        convo = self._store.get_conversation(convo_id)
        if convo:
            self._feed.load_messages(convo.get("messages") or [])
            self._active_conversation_id = convo_id
            self._hide_memory_banner()

    def _load_conversation(self, conversation_id: str):
        convo = self._store.get_conversation(conversation_id)
        if not convo:
            return
        self._active_conversation_id = conversation_id
        self._store.set_active_conversation_id(conversation_id)
        self._feed.load_messages(convo.get("messages") or [])
        self._hide_memory_banner()
        self._refresh_history()
        self._set_tab(0)

    def _new_conversation(self):
        self._active_conversation_id = self._store.create_conversation("New Conversation")
        self._feed.clear_messages()
        self._hide_memory_banner()
        self._refresh_history()
        self._set_tab(0)

    def _clear_current_conversation(self):
        self._new_conversation()

    def _rename_current_conversation(self):
        convo_id = self._ensure_active_conversation()
        convo = self._store.get_conversation(convo_id)
        current = (convo or {}).get("title") or "Conversation"
        title, ok = QInputDialog.getText(self, "Rename Conversation", "Conversation title:", text=current)
        if ok and title.strip():
            self._store.rename_conversation(convo_id, title.strip())
            self._refresh_history()

    def _export_current_conversation(self):
        convo_id = self._ensure_active_conversation()
        convo = self._store.get_conversation(convo_id)
        title = (convo or {}).get("title") or "conversation"
        default = str(BASE_DIR / "downloads" / f"{title}.json")
        path, _ = QFileDialog.getSaveFileName(self, "Export Conversation", default, "JSON Files (*.json)")
        if not path:
            return
        try:
            self._store.export_conversation(convo_id, path)
        except Exception:
            pass

    def _pin_current_conversation(self):
        convo_id = self._ensure_active_conversation()
        convo = self._store.get_conversation(convo_id)
        pinned = not bool((convo or {}).get("pinned"))
        self._store.pin_conversation(convo_id, pinned)
        self._refresh_history()

    def _delete_current_conversation(self):
        convo_id = self._ensure_active_conversation()
        self._store.delete_conversation(convo_id)
        self._active_conversation_id = None
        self._new_conversation()

    def show_at(self):
        self.show_workspace(animate=False)

    def reposition(self):
        if not self.isVisible():
            return
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.right() - self._expanded_w + 1
        y = screen.top() + 18
        h = max(640, screen.height() - 36)
        self.setGeometry(x, y, self._expanded_w, h)
        self._target_h = h
        self._panel.setGeometry(0, 0, self._expanded_w, h)

    def _dock_rect(self) -> QRectF:
        screen = QApplication.primaryScreen().availableGeometry()
        h = max(640, screen.height() - 36)
        y = screen.top() + 18
        w = self._expanded_w
        x = screen.right() - w + 1
        return QRectF(x, y, w, h)

    def _collapsed_rect(self) -> QRectF:
        screen = QApplication.primaryScreen().availableGeometry()
        h = max(640, screen.height() - 36)
        y = screen.top() + 18
        w = self._expanded_w
        x = screen.right() + 8
        return QRectF(x, y, w, h)

    def show_workspace(self, animate: bool = True):
        self._collapsed = False
        self._panel.show()
        self._content.show()
        dock = self._dock_rect()
        start = self._collapsed_rect() if animate else dock
        self.setGeometry(start.toRect())
        self.show()
        self.raise_()
        self.activateWindow()
        self._apply_state()
        if animate:
            self._anim.stop()
            self._anim.setStartValue(start.toRect())
            self._anim.setEndValue(dock.toRect())
            self._anim.start()
        else:
            self.setGeometry(dock.toRect())
        self._panel.setGeometry(0, 0, self.width(), self.height())

    def hide_workspace(self, animate: bool = True):
        self._collapsed = True
        if not self.isVisible():
            self._panel.hide()
            self.hide()
            return
        if animate:
            dock = self.geometry()
            end = self._collapsed_rect()
            self._anim.stop()
            self._anim.setStartValue(dock)
            self._anim.setEndValue(end.toRect())
            self._anim.finished.connect(self._hide_after_anim)
            self._anim.start()
        else:
            self._hide_after_anim()

    def _hide_after_anim(self):
        try:
            self._anim.finished.disconnect(self._hide_after_anim)
        except Exception:
            pass
        self._panel.hide()
        self.hide()

    def toggle_collapsed(self):
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool):
        if bool(collapsed):
            self.hide_workspace(animate=True)
        else:
            self.show_workspace(animate=True)

    def is_collapsed(self) -> bool:
        return self._collapsed

    def _apply_state(self):
        self._panel.setVisible(not self._collapsed)
        self._content.setVisible(not self._collapsed)
        if self.isVisible() and not self._collapsed:
            self.reposition()

    def append_log(self, text: str):
        raw = (text or "").strip()
        if not raw:
            return
        low = raw.lower()
        if low.startswith(("you:", "brahma ai:")):
            return
        if low.startswith("sys:"):
            self.record_chat_event({"role": "system", "text": raw.split(":", 1)[1].strip(), "source": "local"})

    def record_chat_event(self, event: object):
        data = event if isinstance(event, dict) else {}
        role = (data.get("role") or "").strip().lower()
        text = (data.get("text") or data.get("content") or "").strip()
        if not role or not text:
            return
        attachments = data.get("attachments") or []
        stamp = data.get("timestamp")
        convo_id = data.get("conversation_id") or self._active_conversation_id
        if role == "user":
            convo_id = self._store.record_chat("user", text, conversation_id=convo_id, attachments=attachments)
            self._active_conversation_id = convo_id
            self._feed.add_message("user", "You", text, _fmt_time_stamp(stamp), attachments=attachments)
            memories = self._store.search_memories(text)
            self._show_memory_banner(memories)
        elif role == "assistant":
            convo_id = self._store.record_chat("assistant", text, conversation_id=convo_id, attachments=attachments)
            self._active_conversation_id = convo_id
            self._feed.add_message("assistant", "Brahma", text, _fmt_time_stamp(stamp), attachments=attachments, animate=True)
            self._hide_memory_banner()
        elif role == "system":
            convo_id = self._store.record_chat("system", text, conversation_id=convo_id, attachments=attachments)
            self._active_conversation_id = convo_id
            self._feed.add_message("system", "System", text, _fmt_time_stamp(stamp), attachments=attachments, event_type=text)
        elif role == "file":
            convo_id = self._store.record_chat("assistant", text, conversation_id=convo_id, attachments=attachments)
            self._active_conversation_id = convo_id
            self._feed.add_message("file", "Files", text, _fmt_time_stamp(stamp), attachments=attachments)
        self._refresh_history()

    def apply_task_workspace(self, event: object):
        data = event if isinstance(event, dict) else {}
        action = (data.get("action") or "update").strip().lower()
        if action == "start":
            command = data.get("command") or ""
            plan = data.get("plan") or []
            plan_text = plan if isinstance(plan, str) else "\n".join(f"• {item}" for item in plan) if plan else ""
            self._task_card.show()
            self._task_card.start_workspace(command, plan, data.get("source") or "local")
            # Intentionally do not post a 'Task started' system message to the activity feed
            # because the workspace UI already shows the task status.
        elif action == "update":
            self._task_card.show()
            self._task_card.update_workspace(
                title=data.get("title"),
                command=data.get("command"),
                plan=data.get("plan"),
                status=data.get("status"),
                output=data.get("output"),
                percent=data.get("percent"),
                footer=data.get("footer"),
            )
            chunks = [data.get("status") or "", data.get("output") or "", data.get("footer") or ""]
            text = "\n".join(chunk for chunk in chunks if chunk)
            if text:
                self.record_chat_event({"role": "system", "text": text, "source": data.get("source") or "local"})
        elif action == "finish":
            self._task_card.show()
            self._task_card.finish_workspace(
                data.get("result") or data.get("output") or "Done.",
                data.get("status") or "Task completed.",
                int(data.get("percent") or 100),
            )
            self.record_chat_event({
                "role": "system",
                "text": data.get("result") or data.get("output") or "Done.",
                "source": data.get("source") or "local",
            })
        elif action == "clear":
            self._task_card.clear_workspace()

    def _send(self):
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self._ensure_active_conversation(text)
        self.command_submitted.emit(text)


class InlineChatWorkspace(QFrame):
    command_submitted = pyqtSignal(str)
    attach_requested = pyqtSignal()
    mic_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("InlineChatWorkspace")
        self._store = workspace_store()
        self._active_conversation_id: str | None = None
        self.setStyleSheet(
            """
            QFrame#InlineChatWorkspace {
                background: transparent;
                border: none;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(8)
        title = QLabel("CHAT + TASK WORKSPACE")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: #FFFFFF; background: transparent; letter-spacing: 1px;")
        header.addWidget(title)
        header.addStretch(1)
        root.addLayout(header)

        tabs = QHBoxLayout()
        tabs.setSpacing(8)
        self._chat_btn = self._mk_tab("CHAT", True)
        self._history_btn = self._mk_tab("HISTORY", False)
        self._chat_btn.clicked.connect(lambda: self._set_tab(0))
        self._history_btn.clicked.connect(lambda: self._set_tab(1))
        tabs.addWidget(self._chat_btn)
        tabs.addWidget(self._history_btn)
        tabs.addStretch(1)
        root.addLayout(tabs)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_chat_tab())
        self._stack.addWidget(self._build_history_tab())
        root.addWidget(self._stack, 1)

        self._set_tab(0)
        self._ensure_conversation()
        self._load_active_conversation()
        self._refresh_history()

    def _mk_tab(self, text: str, active: bool) -> QPushButton:
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setChecked(active)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(34)
        btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        btn.setStyleSheet(
            """
            QPushButton {
                background: rgba(255,255,255,0.04);
                color: rgba(255,255,255,0.82);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
                padding: 0 14px;
            }
            QPushButton:hover {
                background: rgba(255,69,69,0.08);
                border: 1px solid rgba(255,69,69,0.30);
            }
            """
        )
        return btn

    def _set_tab(self, index: int):
        self._stack.setCurrentIndex(0 if index == 0 else 1)
        self._chat_btn.setChecked(index == 0)
        self._history_btn.setChecked(index == 1)
        if index == 0:
            self._chat_btn.setStyleSheet("""
                QPushButton { background: rgba(255,69,69,0.16); color: #FFFFFF; border: 1px solid rgba(255,69,69,180); border-radius: 10px; padding: 0 14px; }
            """)
            self._history_btn.setStyleSheet("""
                QPushButton { background: rgba(255,255,255,0.04); color: rgba(255,255,255,0.82); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 0 14px; }
                QPushButton:hover { background: rgba(255,69,69,0.08); border: 1px solid rgba(255,69,69,0.30); }
            """)
        else:
            self._history_btn.setStyleSheet("""
                QPushButton { background: rgba(255,69,69,0.16); color: #FFFFFF; border: 1px solid rgba(255,69,69,180); border-radius: 10px; padding: 0 14px; }
            """)
            self._chat_btn.setStyleSheet("""
                QPushButton { background: rgba(255,255,255,0.04); color: rgba(255,255,255,0.82); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 0 14px; }
                QPushButton:hover { background: rgba(255,69,69,0.08); border: 1px solid rgba(255,69,69,0.30); }
            """)

    def _build_chat_tab(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self._task_card = TaskCard()
        self._task_card.hide()
        lay.addWidget(self._task_card)

        self._memory_frame = QFrame()
        self._memory_frame.setVisible(False)
        self._memory_frame.setStyleSheet("""
            QFrame {
                background: rgba(255,69,69,0.05);
                border: 1px solid rgba(255,69,69,0.24);
                border-radius: 12px;
            }
        """)
        mlay = QVBoxLayout(self._memory_frame)
        mlay.setContentsMargins(12, 10, 12, 10)
        mlay.setSpacing(6)
        title = QLabel("Using Memory:")
        title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        title.setStyleSheet("color: #FFFFFF; background: transparent;")
        self._memory_lbl = QLabel("")
        self._memory_lbl.setWordWrap(True)
        self._memory_lbl.setStyleSheet("color: rgba(255,255,255,0.75); background: transparent;")
        mlay.addWidget(title)
        mlay.addWidget(self._memory_lbl)
        lay.addWidget(self._memory_frame)

        self._feed = ConversationFeed()
        lay.addWidget(self._feed, 1)

        # Right sidebar chat is now read-only; commands are entered through the center dashboard command bar.
        return page

    def _build_history_tab(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search conversations...")
        self._search.setFont(QFont("Segoe UI", 10))
        self._search.setFixedHeight(38)
        self._search.setStyleSheet("QLineEdit { background: rgba(10,11,14,205); color: #FFFFFF; border: 1px solid rgba(255,69,69,100); border-radius: 12px; padding: 0 12px; }")
        self._search.textChanged.connect(self._refresh_history)
        lay.addWidget(self._search)
        self._history_scroll = QScrollArea()
        self._history_scroll.setWidgetResizable(True)
        self._history_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._history_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._history_content = QWidget()
        self._history_content.setStyleSheet("background: transparent;")
        self._history_layout = QVBoxLayout(self._history_content)
        self._history_layout.setContentsMargins(0, 0, 0, 0)
        self._history_layout.setSpacing(10)
        self._history_layout.addStretch(1)
        self._history_scroll.setWidget(self._history_content)
        lay.addWidget(self._history_scroll, 1)
        return page

    def _ensure_conversation(self, first_message: str | None = None):
        if self._active_conversation_id:
            convo = self._store.get_conversation(self._active_conversation_id)
            if convo:
                return self._active_conversation_id
        self._active_conversation_id = self._store.ensure_active_conversation(first_message or "")
        return self._active_conversation_id

    def _clear_layout(self, layout: QVBoxLayout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _refresh_history(self, *_):
        search = self._search.text().strip() if hasattr(self, "_search") else ""
        self._clear_layout(self._history_layout)
        groups = self._store.grouped_conversations(search)
        if not groups:
            empty = QLabel("No conversations yet.")
            empty.setStyleSheet("color: rgba(255,255,255,0.60); background: transparent;")
            self._history_layout.addWidget(empty)
            self._history_layout.addStretch(1)
            return
        for group_name, items in groups.items():
            self._history_layout.addWidget(self._group_label(group_name))
            for item in items:
                card = HistoryConversationItem(item["id"], item["title"], _fmt_time_stamp(item["updatedAt"]), pinned=bool(item["pinned"]))
                card.clicked.connect(self._open_conversation)
                self._history_layout.addWidget(card)
        self._history_layout.addStretch(1)

    def _group_label(self, title: str) -> QLabel:
        lbl = QLabel(title.upper())
        lbl.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        lbl.setStyleSheet("color: rgba(255,255,255,0.58); background: transparent; letter-spacing: 1px;")
        return lbl

    def _show_memories(self, memories: list[dict[str, object]]):
        texts = [str(m.get("content") or "").strip() for m in memories if str(m.get("content") or "").strip()]
        if not texts:
            self._memory_lbl.setText("")
            self._memory_frame.hide()
            return
        self._memory_lbl.setText("• " + "\n• ".join(texts[:4]))
        self._memory_frame.show()

    def _hide_memories(self):
        self._memory_lbl.setText("")
        self._memory_frame.hide()

    def _open_conversation(self, conversation_id: str):
        convo = self._store.get_conversation(conversation_id)
        if not convo:
            return
        self._active_conversation_id = conversation_id
        self._store.set_active_conversation_id(conversation_id)
        self._feed.load_messages(convo.get("messages") or [])
        self._hide_memories()
        self._refresh_history()
        self._set_tab(0)

    def _load_active_conversation(self):
        convo_id = self._ensure_conversation()
        convo = self._store.get_conversation(convo_id)
        if convo:
            self._feed.load_messages(convo.get("messages") or [])
        self._refresh_history()

    def record_chat_event(self, event: object):
        data = event if isinstance(event, dict) else {}
        role = (data.get("role") or "").strip().lower()
        text = (data.get("text") or data.get("content") or "").strip()
        if not role or not text:
            return
        convo_id = data.get("conversation_id") or self._ensure_conversation(text if role == "user" else None)
        attachments = data.get("attachments") or []
        stamp = _fmt_time_stamp(data.get("timestamp"))
        if role == "user":
            self._store.record_chat("user", text, conversation_id=convo_id, attachments=attachments)
            self._feed.add_message("user", "You", text, stamp, attachments=attachments)
            self._show_memories(self._store.search_memories(text))
        elif role == "assistant":
            self._store.record_chat("assistant", text, conversation_id=convo_id, attachments=attachments)
            self._feed.add_message("assistant", "Brahma", text, stamp, attachments=attachments)
            self._hide_memories()
        elif role == "system":
            self._store.record_chat("system", text, conversation_id=convo_id, attachments=attachments)
            self._feed.add_message("system", "System", text, stamp, attachments=attachments)
        elif role == "file":
            self._store.record_chat("assistant", text, conversation_id=convo_id, attachments=attachments)
            self._feed.add_message("file", "Files", text, stamp, attachments=attachments)
        self._refresh_history()

    def append_log(self, text: str):
        raw = (text or "").strip()
        if not raw:
            return
        low = raw.lower()
        if low.startswith("sys:"):
            self.record_chat_event({"role": "system", "text": raw.split(":", 1)[1].strip()})

    def apply_task_workspace(self, event: object):
        data = event if isinstance(event, dict) else {}
        action = (data.get("action") or "update").strip().lower()
        if action == "start":
            command = data.get("command") or ""
            plan = data.get("plan") or []
            plan_text = plan if isinstance(plan, str) else "\n".join(f"• {item}" for item in plan) if plan else ""
            self._task_card.start_workspace(command, plan, data.get("source") or "local")
            # Do not emit a 'Task started' system event into the conversation feed.
        elif action == "update":
            self._task_card.update_workspace(
                title=data.get("title"),
                command=data.get("command"),
                plan=data.get("plan"),
                status=data.get("status"),
                output=data.get("output"),
                percent=data.get("percent"),
                footer=data.get("footer"),
            )
            chunks = [data.get("status") or "", data.get("output") or "", data.get("footer") or ""]
            text = "\n".join(chunk for chunk in chunks if chunk)
            if text:
                self.record_chat_event({"role": "system", "text": text, "source": data.get("source") or "local"})
        elif action == "finish":
            self._task_card.finish_workspace(
                data.get("result") or data.get("output") or "Done.",
                data.get("status") or "Task completed.",
                int(data.get("percent") or 100),
            )
            self.record_chat_event({
                "role": "system",
                "text": data.get("result") or data.get("output") or "Done.",
                "source": data.get("source") or "local",
            })
        elif action == "clear":
            self._task_card.clear_workspace()

    def _send(self):
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self._ensure_conversation(text)
        self.command_submitted.emit(text)


class LauncherControlPanel(QDialog):
    def __init__(self, *, startup_workspace: bool = False, on_open=None, on_close=None,
                 on_toggle_startup=None, on_hide_icon=None, on_restart=None, on_quit=None,
                 on_open_app=None,
                 on_show_icon=None, parent=None):
        super().__init__(parent)
        self._on_open = on_open
        self._on_close = on_close
        self._on_toggle_startup = on_toggle_startup
        self._on_hide_icon = on_hide_icon
        self._on_restart = on_restart
        self._on_quit = on_quit
        self._on_open_app = on_open_app
        self._on_show_icon = on_show_icon

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(False)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: rgba(15,15,20,235);
                border: 1px solid rgba(0,191,255,60);
                border-radius: 18px;
            }
        """)
        root.addWidget(frame)

        lay = QVBoxLayout(frame)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)

        title = QLabel("BRAHMA CONTROL")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: #FFFFFF; background: transparent; letter-spacing: 1px;")
        lay.addWidget(title)

        sub = QLabel("Desktop launcher controls")
        sub.setFont(QFont("Segoe UI", 9))
        sub.setStyleSheet("color: rgba(255,255,255,0.65); background: transparent;")
        lay.addWidget(sub)

        def mk_btn(text: str, *, checkable: bool = False, checked: bool = False) -> QPushButton:
            btn = QPushButton(text)
            btn.setCheckable(checkable)
            btn.setChecked(checked)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(36)
            btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255,255,255,0.05);
                    color: #FFFFFF;
                    border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 12px;
                    padding: 6px 12px;
                    text-align: left;
                }
                QPushButton:hover {
                    background: rgba(0,191,255,0.10);
                    border: 1px solid rgba(0,191,255,0.45);
                }
                QPushButton:checked {
                    background: rgba(0,191,255,0.16);
                    border: 1px solid rgba(0,191,255,0.60);
                }
            """)
            return btn

        self._open_btn = mk_btn("Open Workspace")
        self._close_btn = mk_btn("Close Workspace")
        self._startup_btn = mk_btn("Show Workspace On Startup", checkable=True, checked=bool(startup_workspace))
        self._show_icon_btn = mk_btn("Show Floating Icon")
        self._hide_icon_btn = mk_btn("Hide Floating Icon")
        self._restart_btn = mk_btn("Restart Brahma")
        self._quit_btn = mk_btn("Quit Brahma")
        self._open_app_btn = mk_btn("Open App")

        self._open_btn.clicked.connect(lambda: self._invoke(self._on_open))
        self._close_btn.clicked.connect(lambda: self._invoke(self._on_close))
        self._startup_btn.clicked.connect(lambda: self._invoke(self._on_toggle_startup, self._startup_btn.isChecked()))
        self._show_icon_btn.clicked.connect(lambda: self._invoke(self._on_show_icon))
        self._hide_icon_btn.clicked.connect(self._hide_icon_confirm)
        self._restart_btn.clicked.connect(lambda: self._invoke(self._on_restart))
        self._quit_btn.clicked.connect(lambda: self._invoke(self._on_quit))
        self._open_app_btn.clicked.connect(lambda: self._invoke(self._on_open_app))

        for btn in (
            self._open_app_btn, self._open_btn, self._close_btn, self._startup_btn,
            self._show_icon_btn, self._hide_icon_btn, self._restart_btn, self._quit_btn
        ):
            lay.addWidget(btn)

        self.adjustSize()

    def _invoke(self, fn, *args):
        if fn:
            try:
                fn(*args)
            except Exception:
                pass
        self.close()

    def _hide_icon_confirm(self):
        box = QDialog(self)
        box.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        box.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        frame = QFrame()
        frame.setStyleSheet("QFrame { background: rgba(15,15,20,240); border: 1px solid rgba(0,191,255,60); border-radius: 16px; }")
        lay.addWidget(frame)
        flay = QVBoxLayout(frame)
        flay.setContentsMargins(18, 16, 18, 16)
        flay.setSpacing(10)
        lbl = QLabel("Hide Brahma icon?")
        lbl.setStyleSheet("color: #FFFFFF; background: transparent; font: 700 11pt 'Segoe UI';")
        sub = QLabel("You can restore it from the system tray.")
        sub.setStyleSheet("color: rgba(255,255,255,0.65); background: transparent;")
        flay.addWidget(lbl)
        flay.addWidget(sub)
        row = QHBoxLayout()
        cancel = QPushButton("Cancel")
        hide = QPushButton("Hide")
        for btn in (cancel, hide):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(34)
            btn.setStyleSheet("QPushButton { background: rgba(255,255,255,0.05); color: #FFFFFF; border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; } QPushButton:hover { border: 1px solid #00BFFF; }")
        cancel.clicked.connect(box.reject)
        hide.clicked.connect(box.accept)
        row.addWidget(cancel)
        row.addWidget(hide)
        flay.addLayout(row)
        box.adjustSize()
        screen = QApplication.primaryScreen().availableGeometry()
        box.move(screen.center().x() - box.width() // 2, screen.center().y() - box.height() // 2)
        if box.exec():
            self._invoke(self._on_hide_icon)

    def set_startup_workspace(self, enabled: bool):
        self._startup_btn.setChecked(bool(enabled))


class SmallPanelCard(QFrame):
    def __init__(self, title: str, body: str, *, accent: str = C.WHITE, parent=None):
        super().__init__(parent)
        self.setObjectName("SmallPanelCard")
        self.setStyleSheet(
            f"""
            QFrame#SmallPanelCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(16, 18, 24, 230),
                    stop:1 rgba(9, 11, 15, 210));
                border: 1px solid rgba(255, 255, 255, 0.16);
                border-radius: 14px;
            }}
            """
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)

        t = QLabel(title.upper())
        t.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        t.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent; letter-spacing: 1px;")
        lay.addWidget(t)

        self._body_lbl = QLabel(body)
        self._body_lbl.setWordWrap(True)
        self._body_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._body_lbl.setStyleSheet(f"color: {accent}; background: transparent;")
        lay.addWidget(self._body_lbl)

    def set_body(self, body: str):
        self._body_lbl.setText(body)


class StatCard(QFrame):
    def __init__(self, label: str, value: str, parent=None):
        super().__init__(parent)
        self.setObjectName("StatCard")
        self.setStyleSheet(
            f"""
            QFrame#StatCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(18, 20, 26, 240),
                    stop:1 rgba(8, 10, 14, 220));
                border: 1px solid rgba(255, 255, 255, 0.14);
                border-radius: 16px;
            }}
            """
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)
        lbl = QLabel(label.upper())
        lbl.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        val = QLabel(value)
        val.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        val.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        self._detail_lbl = QLabel("")
        self._detail_lbl.setFont(QFont("Segoe UI", 7))
        self._detail_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
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
                background: {C.WHITE};
                border-radius: 2px;
            }}
            """
        )
        lay.addWidget(lbl)
        lay.addWidget(val)
        lay.addWidget(self._detail_lbl)
        lay.addWidget(self._bar)
        self._value_lbl = val

    def set_value(self, value: str, level: int | None = None, detail: str | None = None):
        self._value_lbl.setText(value)
        if detail is not None:
            self._detail_lbl.setText(detail)
        if level is not None:
            self._bar.setValue(max(0, min(100, int(level))))


class LogWidget(QScrollArea):
    _sig = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet(
            f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                border: none;
                margin: 6px 0 6px 0;
            }}
            QScrollBar::handle:vertical {{
                background: {C.BORDER_B};
                border-radius: 4px;
                min-height: 24px;
            }}
            """
        )
        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(10)
        self._layout.addStretch(1)
        self.setWidget(self._content)

        self._sig.connect(self._enqueue)

    def append_log(self, text: str):
        self._sig.emit(text)

    def _enqueue(self, text: str):
        role, name, body = self._parse(text)
        stamp = time.strftime("%H:%M")

        card = MessageCard(role, name, body, stamp)
        self._layout.insertWidget(self._layout.count() - 1, card)
        QTimer.singleShot(0, self._scroll_bottom)

    def _scroll_bottom(self):
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _parse(self, text: str) -> tuple[str, str, str]:
        raw = (text or "").strip()
        tl = raw.lower()
        if tl.startswith("you:"):
            return "user", "You", raw[4:].strip()
        if tl.startswith("brahma ai:"):
            return "assistant", "Brahma", raw[len("Brahma AI:"):].strip()
        if tl.startswith("brahma:"):
            return "assistant", "Brahma", raw[len("Brahma:"):].strip()
        if tl.startswith("file:"):
            return "file", "File", raw[5:].strip()
        if tl.startswith("err:"):
            return "error", "System", raw[4:].strip()
        if tl.startswith("sys:"):
            return "system", "System", raw[4:].strip()
        return "system", "System", raw

_FILE_ICONS = {
    "image":   ("ðŸ-¼", "#00d4ff"), "video":   ("ðŸŽ¬", "#ff6b00"),
    "audio":   ("ðŸŽµ", "#cc44ff"), "pdf":     ("ðŸ“„", "#ff4444"),
    "word":    ("ðŸ“", "#4488ff"), "excel":   ("ðŸ“Š", "#44bb44"),
    "code":    ("ðŸ’»", "#ffcc00"), "archive": ("ðŸ“¦", "#ff8844"),
    "pptx":    ("ðŸ“Š", "#ff6622"), "text":    ("ðŸ“ƒ", "#aaaaaa"),
    "data":    ("ðŸ”§", "#88ddff"), "unknown": ("ðŸ“Ž", "#888888"),
}
_EXT_TO_CAT = {
    **dict.fromkeys(["jpg","jpeg","png","gif","webp","bmp","tiff","svg","ico"], "image"),
    **dict.fromkeys(["mp4","avi","mov","mkv","wmv","flv","webm","m4v"],         "video"),
    **dict.fromkeys(["mp3","wav","ogg","m4a","aac","flac","wma","opus"],        "audio"),
    **dict.fromkeys(["pdf"],                                                     "pdf"),
    **dict.fromkeys(["doc","docx"],                                              "word"),
    **dict.fromkeys(["xls","xlsx","ods"],                                        "excel"),
    **dict.fromkeys(["ppt","pptx"],                                              "pptx"),
    **dict.fromkeys(["py","js","ts","jsx","tsx","html","css","java","c","cpp",
                     "cs","go","rs","rb","php","swift","kt","sh","sql","lua"],   "code"),
    **dict.fromkeys(["zip","rar","tar","gz","7z","bz2","xz"],                   "archive"),
    **dict.fromkeys(["txt","md","rst","log"],                                    "text"),
    **dict.fromkeys(["csv","tsv","json","xml"],                                  "data"),
}

def _file_category(path: Path) -> str:
    return _EXT_TO_CAT.get(path.suffix.lower().lstrip("."), "unknown")

def _fmt_size(size: int) -> str:
    if   size < 1024:    return f"{size} B"
    elif size < 1024**2: return f"{size/1024:.1f} KB"
    elif size < 1024**3: return f"{size/1024**2:.1f} MB"
    else:                return f"{size/1024**3:.1f} GB"


class FileDropZone(QWidget):
    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(100)
        self._current_file: str | None = None
        self._hovering  = False
        self._drag_over = False
        self._dash_offset = 0.0
        self._anim_tmr = QTimer(self)
        self._anim_tmr.timeout.connect(self._animate)
        self._anim_tmr.start(40)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._canvas = _DropCanvas(self)
        layout.addWidget(self._canvas)

    def _animate(self):
        self._dash_offset = (self._dash_offset + 0.8) % 20
        self._canvas.update()

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._drag_over = True; self._canvas.update()

    def dragLeaveEvent(self, e):
        self._drag_over = False; self._canvas.update()

    def dropEvent(self, e: QDropEvent):
        self._drag_over = False
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if Path(path).is_file():
                self._set_file(path)
        self._canvas.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._browse()

    def enterEvent(self, e):
        self._hovering = True; self._canvas.update()

    def leaveEvent(self, e):
        self._hovering = False; self._canvas.update()

    def current_file(self) -> str | None:
        return self._current_file

    def clear_file(self):
        self._current_file = None; self._canvas.update()

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a file for Brahma AI", str(Path.home()),
            "All Files (*.*);;"
            "Images (*.jpg *.jpeg *.png *.gif *.webp *.bmp *.svg);;"
            "Documents (*.pdf *.docx *.txt *.md *.pptx);;"
            "Data (*.csv *.xlsx *.json *.xml);;"
            "Code (*.py *.js *.ts *.html *.css *.java *.cpp *.go);;"
            "Audio (*.mp3 *.wav *.ogg *.m4a *.aac *.flac);;"
            "Video (*.mp4 *.avi *.mov *.mkv *.wmv *.webm);;"
            "Archives (*.zip *.rar *.tar *.gz *.7z)",
        )
        if path:
            self._set_file(path)

    def _set_file(self, path: str):
        self._current_file = path
        self._canvas.update()
        self.file_selected.emit(path)


class _DropCanvas(QWidget):
    def __init__(self, zone: FileDropZone):
        super().__init__(zone)
        self._z = zone

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        z    = self._z
        W, H = self.width(), self.height()
        pad  = 6
        rect = QRectF(pad, pad, W - pad * 2, H - pad * 2)

        bg_col = qcol("#001a24" if z._drag_over else ("#001218" if z._hovering else C.PANEL))
        p.setBrush(QBrush(bg_col)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect, 6, 6)

        if z._current_file:   border_col = qcol(C.GREEN, 200)
        elif z._drag_over:    border_col = qcol(C.PRI, 230)
        elif z._hovering:     border_col = qcol(C.BORDER_B, 200)
        else:                 border_col = qcol(C.BORDER, 160)

        pen = QPen(border_col, 1.5, Qt.PenStyle.DashLine)
        pen.setDashOffset(z._dash_offset)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 6, 6)

        if z._current_file:   self._paint_file(p, W, H)
        elif z._drag_over:    self._paint_drag_over(p, W, H)
        else:                 self._paint_idle(p, W, H, z._hovering)

    def _paint_idle(self, p, W, H, hover):
        cx, cy = W / 2, H / 2
        col = qcol(C.PRI_DIM if not hover else C.PRI)
        p.setPen(QPen(col, 2)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(cx, cy - 14), QPointF(cx, cy + 4))
        p.drawLine(QPointF(cx - 8, cy - 6), QPointF(cx, cy - 14))
        p.drawLine(QPointF(cx + 8, cy - 6), QPointF(cx, cy - 14))
        p.drawLine(QPointF(cx - 14, cy + 4), QPointF(cx + 14, cy + 4))
        p.setFont(QFont("Courier New", 8))
        p.setPen(QPen(qcol(C.PRI_DIM if not hover else C.TEXT), 1))
        p.drawText(QRectF(0, cy + 8, W, 16), Qt.AlignmentFlag.AlignCenter,
                   "Drop file here  or  Click to Browse")
        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(qcol("#1a4a5a"), 1))
        p.drawText(QRectF(0, cy + 24, W, 14), Qt.AlignmentFlag.AlignCenter,
                   "Images Â· Video Â· Audio Â· PDF Â· Docs Â· Code Â· Data")

    def _paint_drag_over(self, p, W, H):
        cx, cy = W / 2, H / 2
        p.setFont(QFont("Courier New", 20))
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(0, cy - 24, W, 32), Qt.AlignmentFlag.AlignCenter, "â¬‡")
        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(0, cy + 12, W, 16), Qt.AlignmentFlag.AlignCenter, "Release to load")

    def _paint_file(self, p, W, H):
        path = Path(self._z._current_file)
        cat  = _file_category(path)
        icon, icon_col = _FILE_ICONS.get(cat, _FILE_ICONS["unknown"])
        size_str = _fmt_size(path.stat().st_size)
        ext_str  = path.suffix.upper().lstrip(".") or "FILE"

        block_x, block_w = 10, 60
        p.setFont(QFont("Segoe UI Emoji", 22) if _OS == "Windows" else QFont("Arial", 22))
        p.setPen(QPen(qcol(icon_col), 1))
        p.drawText(QRectF(block_x, 0, block_w, H), Qt.AlignmentFlag.AlignCenter, icon)

        tx = block_x + block_w + 6
        tw = W - tx - 38

        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.WHITE), 1))
        name = path.name if len(path.name) <= 34 else path.name[:31] + "..."
        p.drawText(QRectF(tx, H * 0.18, tw, 16),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(tx, H * 0.18 + 18, tw, 14),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"{ext_str}  Â·  {size_str}")

        p.setFont(QFont("Courier New", 6))
        p.setPen(QPen(qcol("#1e5c6a"), 1))
        par = str(path.parent)
        if len(par) > 42: par = "â€¦" + par[-41:]
        p.drawText(QRectF(tx, H * 0.18 + 34, tw, 12),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, par)

        p.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.RED, 180), 1))
        p.drawText(QRectF(W - 34, 0, 28, H), Qt.AlignmentFlag.AlignCenter, "âœ•")

    def mousePressEvent(self, e):
        z = self._z
        if z._current_file and e.pos().x() > self.width() - 34:
            z.clear_file()
        else:
            z.mousePressEvent(e)


class SetupOverlay(QWidget):
    done = pyqtSignal(str, str, str)

    def __init__(self, parent=None, defaults: dict | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            SetupOverlay {{
                background: rgba(0, 6, 10, 245);
                border: 1px solid {C.BORDER_B};
                border-radius: 6px;
            }}
        """)

        defaults = defaults or {}

        detected = {"darwin": "mac", "windows": "windows"}.get(
            _OS.lower(), "linux"
        )
        self._sel_os = detected

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 22, 30, 22)
        layout.setSpacing(8)

        def _lbl(txt, font_size=9, bold=False, color=C.PRI,
                 align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt)
            w.setAlignment(align)
            w.setFont(QFont("Courier New", font_size,
                            QFont.Weight.Bold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        layout.addWidget(_lbl("â—ˆ  INITIALISATION REQUIRED", 13, True))
        layout.addWidget(_lbl("Configure Brahma before first boot.", 9, color=C.PRI_DIM))
        layout.addSpacing(6)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER};"); layout.addWidget(sep)
        layout.addSpacing(4)

        layout.addWidget(_lbl("GEMINI API KEY", 8, color=C.TEXT_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))
        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText("AIzaâ€¦")
        self._key_input.setFont(QFont("Courier New", 10))
        self._key_input.setFixedHeight(32)
        self._key_input.setStyleSheet(f"""
            QLineEdit {{
                background: #000d12; color: {C.TEXT};
                border: 1px solid {C.BORDER}; border-radius: 3px; padding: 4px 8px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
        """)
        layout.addWidget(self._key_input)
        self._key_input.setText((defaults.get("gemini_api_key") or "").strip())
        layout.addSpacing(8)

        layout.addWidget(_lbl("OPENROUTER API KEY", 8, color=C.TEXT_DIM,
                       align=Qt.AlignmentFlag.AlignLeft))
        self._or_input = QLineEdit()
        self._or_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._or_input.setPlaceholderText("sk-or-â€¦")
        self._or_input.setFont(QFont("Courier New", 10))
        self._or_input.setFixedHeight(32)
        self._or_input.setStyleSheet(f"""
            QLineEdit {{
                background: #000d12; color: {C.TEXT};
                border: 1px solid {C.BORDER}; border-radius: 3px; padding: 4px 8px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.ACC2}; }}
        """)
        layout.addWidget(self._or_input)
        self._or_input.setText((defaults.get("openrouter_api_key") or "").strip())

        layout.addSpacing(12)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C.BORDER};"); layout.addWidget(sep2)
        layout.addSpacing(4)

        layout.addWidget(_lbl("OPERATING SYSTEM", 8, color=C.TEXT_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))
        os_default = (defaults.get("os_system") or detected).strip().lower()
        if os_default not in {"windows", "mac", "linux"}:
            os_default = detected
        det_name = {"windows": "Windows", "mac": "macOS", "linux": "Linux"}[detected]
        layout.addWidget(_lbl(f"Auto-detected: {det_name}", 8, color=C.ACC2,
                               align=Qt.AlignmentFlag.AlignLeft))

        os_row = QHBoxLayout(); os_row.setSpacing(6)
        self._os_btns: dict[str, QPushButton] = {}
        for key, label in [("windows","âŠž  Windows"),("mac","  macOS"),("linux","ðŸ§  Linux")]:
            btn = QPushButton(label)
            btn.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
            btn.setFixedHeight(32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._sel(k))
            os_row.addWidget(btn)
            self._os_btns[key] = btn
        layout.addLayout(os_row)
        self._sel(os_default)
        layout.addSpacing(12)

        self._status = QLabel("Enter your Gemini key to continue. OpenRouter is optional.")
        self._status.setWordWrap(True)
        self._status.setFont(QFont("Courier New", 8))
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        layout.addWidget(self._status)
        layout.addSpacing(8)

        init_btn = QPushButton("â-¸  INITIALISE SYSTEMS")
        init_btn.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        init_btn.setFixedHeight(36)
        init_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        init_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 3px;
            }}
            QPushButton:hover {{
                background: {C.PRI_GHO}; border: 1px solid {C.PRI};
            }}
        """)
        init_btn.clicked.connect(self._submit)
        layout.addWidget(init_btn)

    def _sel(self, key: str):
        self._sel_os = key
        pal = {"windows":(C.PRI,"#001a22"),"mac":(C.ACC2,"#1a1400"),"linux":(C.GREEN,"#001a0d")}
        for k, btn in self._os_btns.items():
            if k == key:
                fg, bg = pal[k]
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {fg}; color: {bg};
                        border: none; border-radius: 3px; font-weight: bold;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: #000d12; color: {C.TEXT_DIM};
                        border: 1px solid {C.BORDER}; border-radius: 3px;
                    }}
                    QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_B}; }}
                """)

    def _submit(self):
        key = self._key_input.text().strip()
        or_key = self._or_input.text().strip()
        if not key:
            self._key_input.setStyleSheet(
                self._key_input.styleSheet() +
                f" QLineEdit {{ border: 1px solid {C.RED}; }}"
            )
            self._status.setText("Gemini key is required.")
            return
        if or_key and not or_key.startswith("sk-or-"):
            self._status.setText("OpenRouter key looks invalid. Continuing with Gemini only.")
            or_key = ""
        else:
            self._status.setText("Saving settings...")
        self.done.emit(key, or_key, self._sel_os)


class CommandBar(QWidget):
    submitted = pyqtSignal(str)
    attach_clicked = pyqtSignal()
    mic_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setObjectName("CommandBar")
        self.setFixedSize(410, 72)
        self.setStyleSheet("background: transparent;")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        frame = QFrame()
        frame.setObjectName("CommandBarFrame")
        frame.setStyleSheet(f"""
            QFrame#CommandBarFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(8, 8, 8, 248),
                    stop:0.5 rgba(15, 15, 15, 248),
                    stop:1 rgba(8, 8, 8, 248));
                border: 1px solid {C.BORDER_B};
                border-radius: 18px;
            }}
        """)
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)

        lay.addWidget(_framed_logo(36, 24, bg="rgba(255,255,255,0.04)", border=C.BORDER_B, radius=18, inset=5))

        self._input = QLineEdit()
        self._input.setPlaceholderText("Tell Brahma what to do...")
        self._input.setFont(QFont("Segoe UI", 10))
        self._input.setFixedHeight(40)
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(16,16,16,240);
                color: {C.WHITE};
                border: 1px solid {C.BORDER};
                border-radius: 14px;
                padding: 0 14px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.BORDER_B}; }}
        """)
        self._input.returnPressed.connect(self._submit)
        lay.addWidget(self._input, stretch=1)

        attach = QPushButton()
        attach.setFixedSize(40, 40)
        attach.setCursor(Qt.CursorShape.PointingHandCursor)
        attach.setToolTip("Attach file")
        attach.setIcon(QIcon(_icon_pixmap("attach", 18)))
        attach.setIconSize(QSize(18, 18))
        attach.setStyleSheet(f"""
            QPushButton {{
                background: rgba(18,18,18,240);
                color: {C.WHITE};
                border: 1px solid {C.BORDER_B};
                border-radius: 12px;
            }}
            QPushButton:hover {{
                background: rgba(28,28,28,245);
                border: 1px solid {C.WHITE};
            }}
        """)
        attach.clicked.connect(self.attach_clicked.emit)
        lay.addWidget(attach)

        mic = QPushButton()
        mic.setFixedSize(40, 40)
        mic.setCursor(Qt.CursorShape.PointingHandCursor)
        mic.setToolTip("Microphone")
        mic.setIcon(QIcon(_icon_pixmap("mic", 18)))
        mic.setIconSize(QSize(18, 18))
        mic.setStyleSheet(f"""
            QPushButton {{
                background: rgba(18,18,18,240);
                color: {C.WHITE};
                border: 1px solid {C.BORDER_B};
                border-radius: 12px;
            }}
            QPushButton:hover {{
                background: rgba(28,28,28,245);
                border: 1px solid {C.WHITE};
            }}
        """)
        mic.clicked.connect(self.mic_clicked.emit)
        lay.addWidget(mic)

        send = QPushButton()
        send.setFixedSize(40, 40)
        send.setCursor(Qt.CursorShape.PointingHandCursor)
        send.setToolTip("Send")
        send.setIcon(QIcon(_icon_pixmap("send", 18)))
        send.setIconSize(QSize(18, 18))
        send.setStyleSheet(f"""
            QPushButton {{
                background: rgba(24,24,24,240);
                color: {C.WHITE};
                border: 1px solid {C.BORDER_B};
                border-radius: 12px;
            }}
            QPushButton:hover {{
                background: rgba(34,34,34,245);
                border: 1px solid {C.WHITE};
            }}
        """)
        send.clicked.connect(self._submit)
        lay.addWidget(send)

        _attach_pulse_glow(frame, color=C.PRI, blur_min=16.0, blur_max=28.0, alpha=120, period_ms=2800)

        root.addWidget(frame)

    def show_near(self, anchor: QWidget):
        screen = QApplication.primaryScreen().availableGeometry()
        geo = anchor.geometry()
        x = geo.center().x() - (self.width() // 2)
        y = geo.bottom() + 14
        x = max(screen.left() + 12, min(x, screen.right() - self.width() - 12))
        y = max(screen.top() + 12, min(y, screen.bottom() - self.height() - 12))
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
        self._input.setFocus()
        self._input.selectAll()

    def hideEvent(self, event):
        super().hideEvent(event)

    def _submit(self):
        txt = self._input.text().strip()
        if not txt:
            return
        self._input.clear()
        self.submitted.emit(txt)
        self.hide()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)


class ScanningOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._phase = 0.0
        self._text = "SCANNING SCREEN"
        self._sub = "Analyzing display..."

        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._tick)
        self._tmr.start(16)

        # splash + boot UI state
        self._mode = "splash"  # splash -> boot
        self._steps: list[tuple[str, QLabel]] = []
        self._progress_val = 0
        self._progress_tip = ""

        self._center = QFrame(self)
        self._center.setStyleSheet("background: transparent; border: none;")
        self._center_lay = QVBoxLayout(self._center)
        self._center_lay.setContentsMargins(36, 36, 36, 36)
        self._center_lay.setSpacing(18)

        # Splash widgets
        self._splash_logo = QLabel()
        self._splash_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._splash_logo.setPixmap(_logo_pixmap(160))
        self._splash_title = QLabel("BRAHMA AI LITE")
        self._splash_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._splash_title.setFont(QFont("Segoe UI", 18, QFont.Weight.Black))
        self._splash_title.setStyleSheet("color: #ffffff; letter-spacing: 2px;")
        self._splash_sub = QLabel("Your Intelligent Desktop Assistant")
        self._splash_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._splash_sub.setStyleSheet(f"color: {C.TEXT_DIM};")
        self._splash_slogan = QLabel("Think. Command. Accomplish.")
        self._splash_slogan.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._splash_slogan.setStyleSheet(f"color: {C.PRI}; font-weight: 700;")
        self._splash_status = QLabel("Initializing Brahma...")
        self._splash_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._splash_status.setStyleSheet(f"color: {C.TEXT_MED};")

        # Boot widgets
        self._boot_title = QLabel("BRAHMA AI LITE")
        self._boot_title.setFont(QFont("Segoe UI", 20, QFont.Weight.Black))
        self._boot_title.setStyleSheet(f"color: {C.WHITE};")
        self._boot_sub = QLabel("System Boot Sequence")
        self._boot_sub.setStyleSheet(f"color: {C.TEXT_DIM};")

        self._checklist_frame = QFrame()
        self._checklist_frame.setStyleSheet("background: transparent; border: none;")
        self._checklist_lay = QVBoxLayout(self._checklist_frame)
        self._checklist_lay.setSpacing(8)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(14)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet(
            "QProgressBar { background: rgba(255,255,255,0.04); border-radius: 8px; }"
            "QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 rgba(255,69,69,220), stop:1 rgba(255,120,120,220)); border-radius: 8px; }"
        )

        self._progress_tip_lbl = QLabel("")
        self._progress_tip_lbl.setStyleSheet(f"color: {C.TEXT_DIM};")

        # Layout initial splash
        self._center_lay.addWidget(self._splash_logo)
        self._center_lay.addWidget(self._splash_title)
        self._center_lay.addWidget(self._splash_sub)
        self._center_lay.addWidget(self._splash_slogan)
        self._center_lay.addWidget(self._splash_status)

        self._center.setFixedWidth(820)
        self._center.adjustSize()

        # auto transition from splash to boot
        QTimer.singleShot(1700, self._enter_boot_mode)

    def set_message(self, text: str, sub: str | None = None):
        self._text = (text or "SCANNING SCREEN").upper()
        if sub is not None:
            self._sub = sub
        self.update()

    def show_fullscreen(self, text: str = "SCANNING SCREEN", sub: str = "Analyzing display..."):
        self.set_message(text, sub)
        screen = QApplication.primaryScreen()
        geo = screen.geometry() if screen else QRectF(0, 0, 1280, 720).toRect()
        self.setGeometry(geo)
        self.show()
        self.raise_()

    def hide_overlay(self):
        self.hide()

    def _tick(self):
        self._phase = (self._phase + 0.012) % 1.0
        if self.isVisible():
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        p.fillRect(rect, QColor(0, 0, 0, 185))

        # subtle grid
        grid_pen = QPen(qcol(C.WHITE, 12), 1)
        p.setPen(grid_pen)
        step = 64
        for x in range(0, rect.width(), step):
            p.drawLine(x, 0, x, rect.height())
        for y in range(0, rect.height(), step):
            p.drawLine(0, y, rect.width(), y)

        # blue-white scan beam
        y = int(rect.height() * self._phase)
        beam = QLinearGradient(0, y - 140, 0, y + 140)
        beam.setColorAt(0.0, QColor(120, 210, 255, 0))
        beam.setColorAt(0.48, QColor(120, 210, 255, 90))
        beam.setColorAt(0.50, QColor(255, 255, 255, 180))
        beam.setColorAt(0.52, QColor(120, 210, 255, 90))
        beam.setColorAt(1.0, QColor(120, 210, 255, 0))
        p.fillRect(QRectF(0, y - 140, rect.width(), 280), beam)

        # corner brackets
        p.setPen(QPen(QColor(255, 255, 255, 220), 2))
        br = 28
        for x, y0, dx, dy in [
            (20, 20, 1, 1),
            (rect.width() - 20, 20, -1, 1),
            (20, rect.height() - 20, 1, -1),
            (rect.width() - 20, rect.height() - 20, -1, -1),
        ]:
            p.drawLine(QPointF(x, y0), QPointF(x + dx * br, y0))
            p.drawLine(QPointF(x, y0), QPointF(x, y0 + dy * br))

        # center orb glow
        cx, cy = rect.width() / 2, rect.height() / 2
        for i in range(6):
            r = 110 + i * 22
            alpha = 28 - i * 3
            p.setPen(QPen(QColor(80, 170, 255, max(0, alpha)), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # text
        title_font = QFont("Segoe UI", 20, QFont.Weight.Bold)
        sub_font = QFont("Segoe UI", 10)
        p.setPen(QColor(255, 255, 255, 235))
        p.setFont(title_font)
        p.drawText(QRectF(0, cy - 26, rect.width(), 40), Qt.AlignmentFlag.AlignCenter, self._text)
        p.setFont(sub_font)
        p.setPen(QColor(190, 220, 255, 210))
        p.drawText(QRectF(0, cy + 18, rect.width(), 28), Qt.AlignmentFlag.AlignCenter, self._sub)


class BootSequenceOverlay(QWidget):
    finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setWindowOpacity(0.0)

        self._device_name = "DEVICE"
        self._greeting_name = "Suryaansh"
        self._phase = 0
        self._phase_text = ""
        self._sub_text = ""
        self._scan_lines = [
            "CPU READY",
            "MEMORY READY",
            "NETWORK ONLINE",
            "AI CORE ONLINE",
        ]
        self._scan_active = False
        self._zoom = 1.0
        self._rotation = 0.0
        self._beam = 0.0
        self._particles: list[dict[str, float]] = []
        self._running = False
        self._skip_requested = False
        self._fade_in_anim: QPropertyAnimation | None = None
        self._fade_out_anim: QPropertyAnimation | None = None
        self._zoom_anim: QPropertyAnimation | None = None
        self._phase_timers: list[QTimer] = []

        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._tick)
        self._tmr.start(16)

    def zoom(self) -> float:
        return self._zoom

    def setZoom(self, value: float):
        self._zoom = max(0.08, float(value))
        self.update()

    zoom = pyqtProperty(float, fget=zoom, fset=setZoom)

    def _spawn_particles(self, count: int = 64):
        rect = self.rect()
        if rect.width() <= 0 or rect.height() <= 0:
            return
        cx, cy = rect.width() / 2, rect.height() / 2
        self._particles = []
        for _ in range(count):
            ang = random.uniform(0, math.tau)
            radius = random.uniform(56, 220)
            speed = random.uniform(0.3, 1.2)
            self._particles.append({
                "x": cx + math.cos(ang) * radius,
                "y": cy + math.sin(ang) * radius,
                "dx": math.cos(ang + random.uniform(-0.4, 0.4)) * speed,
                "dy": math.sin(ang + random.uniform(-0.4, 0.4)) * speed,
                "a": random.uniform(90, 220),
                "s": random.uniform(1.2, 2.2),
            })

    def start(self, device_name: str, greeting_name: str = "Suryaansh"):
        self._device_name = (device_name or "DEVICE").strip().upper()
        self._greeting_name = (greeting_name or "Suryaansh").strip() or "Suryaansh"
        self._phase = 0
        self._phase_text = "WELCOME"
        self._sub_text = f"WELCOME, {self._device_name}"
        self._scan_active = False
        self._running = True
        self._skip_requested = False
        self._zoom = 1.0
        self._rotation = 0.0
        self._beam = 0.0
        self._spawn_particles()

        screen = QApplication.primaryScreen()
        geo = screen.geometry() if screen else QRectF(0, 0, 1280, 720).toRect()
        self.setGeometry(geo)
        # position the center frame in the middle of the overlay
        try:
            self._center.setParent(self)
            ch = self._center.sizeHint().height() or self._center.height()
            cw = self._center.width() or self._center.sizeHint().width()
            x = max(0, int((geo.width() - cw) / 2))
            y = max(0, int((geo.height() - ch) / 2) - 40)
            self._center.move(x, y)
            self._center.show()
        except Exception:
            pass
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)

        self.setWindowOpacity(0.0)
        self._fade_in_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_in_anim.setDuration(260)
        self._fade_in_anim.setStartValue(0.0)
        self._fade_in_anim.setEndValue(1.0)
        self._fade_in_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_in_anim.start()

        self._phase_timers.clear()
        self._schedule(1200, self._phase_initializing)
        self._schedule(2000, self._phase_loading)
        self._schedule(2700, self._phase_system_ready)
        self._schedule(3500, self._phase_scan)
        self._schedule(4300, self._phase_greeting)
        self._schedule(4850, self._finish_sequence)

    def _schedule(self, ms: int, fn):
        t = QTimer(self)
        t.setSingleShot(True)
        t.timeout.connect(fn)
        t.start(ms)
        self._phase_timers.append(t)

    def _set_phase(self, phase: int, title: str, sub: str = ""):
        self._phase = phase
        self._phase_text = title
        self._sub_text = sub
        self.update()

    def _phase_initializing(self):
        if self._skip_requested:
            return
        self._set_phase(1, "BRAHMA INITIALIZING...", "Brahma Core waking up.")

    def _phase_loading(self):
        if self._skip_requested:
            return
        self._set_phase(1, "LOADING MODULES...", "Preparing voice, memory, and vision.")

    def _phase_system_ready(self):
        if self._skip_requested:
            return
        self._set_phase(2, "SYSTEM READY", "CPU READY  -  MEMORY READY  -  NETWORK ONLINE  -  AI CORE ONLINE")

    def _phase_scan(self):
        if self._skip_requested:
            return
        self._phase = 2
        self._scan_active = True
        self._sub_text = "CPU READY  -  MEMORY READY  -  NETWORK ONLINE  -  AI CORE ONLINE"
        self.update()

    def _phase_greeting(self):
        if self._skip_requested:
            return
        hour = time.localtime().tm_hour
        if 5 <= hour < 12:
            greet = "Good Morning"
        elif 12 <= hour < 18:
            greet = "Good Afternoon"
        else:
            greet = "Good Evening"
        self._set_phase(3, f"{greet}, {self._greeting_name}", "Brahma Lite is ready.")

    def _finish_sequence(self):
        if self._skip_requested:
            return
        self._running = False
        self._zoom_anim = QPropertyAnimation(self, b"zoom", self)
        self._zoom_anim.setDuration(380)
        self._zoom_anim.setStartValue(self._zoom)
        self._zoom_anim.setEndValue(0.22)
        self._zoom_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._zoom_anim.start()

        self._fade_out_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_out_anim.setDuration(380)
        self._fade_out_anim.setStartValue(1.0)
        self._fade_out_anim.setEndValue(0.0)
        self._fade_out_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._fade_out_anim.finished.connect(self._done)
        self._fade_out_anim.start()

    def _done(self):
        self.hide()
        self.finished.emit()

    def _skip(self):
        if self._skip_requested:
            return
        self._skip_requested = True
        for t in self._phase_timers:
            try:
                t.stop()
            except Exception:
                pass
        self._running = False
        self.setWindowOpacity(0.0)
        self.hide()
        self.finished.emit()

    def _tick(self):
        if not self.isVisible():
            return
        self._rotation = (self._rotation + 0.7) % 360.0
        self._beam = (self._beam + 2.6) % max(1, self.height())
        for p in self._particles:
            p["x"] += p["dx"] * self._zoom
            p["y"] += p["dy"] * self._zoom
            p["a"] = max(40.0, min(220.0, p["a"] + random.uniform(-3, 3)))
        if self._scan_active:
            self._beam = (self._beam + 3.4) % max(1, self.height())
        self.update()

    def _enter_boot_mode(self):
        if not self._running:
            return
        if self._mode == "boot":
            return
        self._mode = "boot"
        # remove splash widgets
        for w in (self._splash_logo, self._splash_title, self._splash_sub, self._splash_slogan, self._splash_status):
            try:
                self._center_lay.removeWidget(w)
                w.hide()
            except Exception:
                pass
        # add boot widgets
        self._center_lay.addWidget(self._boot_title)
        self._center_lay.addWidget(self._boot_sub)
        self._center_lay.addWidget(self._checklist_frame)
        self._center_lay.addWidget(self._progress_bar)
        self._center_lay.addWidget(self._progress_tip_lbl)
        self._center.adjustSize()

    # API to drive startup from backend
    def add_step(self, text: str):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        lbl.setFont(QFont("Segoe UI", 10))
        self._checklist_lay.addWidget(lbl)
        self._steps.append((text, lbl))
        return lbl

    def set_step_status(self, text: str, status: str):
        for t, lbl in self._steps:
            if t == text:
                if status == "done":
                    lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent;")
                    lbl.setText(f"✓ {t}")
                elif status == "in_progress":
                    lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")
                    lbl.setText(f"→ {t}")
                elif status == "failed":
                    lbl.setStyleSheet(f"color: {C.RED}; background: transparent;")
                    lbl.setText(f"✖ {t}")
                else:
                    lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
                    lbl.setText(f"  {t}")
                break

    def set_progress(self, percent: int, tip: str | None = None):
        self._progress_val = max(0, min(100, int(percent)))
        try:
            self._progress_bar.setValue(self._progress_val)
        except Exception:
            pass
        if tip is not None:
            self._progress_tip = tip
            try:
                self._progress_tip_lbl.setText(tip)
            except Exception:
                pass
        if self._progress_val >= 100:
            QTimer.singleShot(600, self._finish)

    def _finish(self):
        self._running = False
        self._fade_out_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_out_anim.setDuration(380)
        self._fade_out_anim.setStartValue(1.0)
        self._fade_out_anim.setEndValue(0.0)
        self._fade_out_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._fade_out_anim.finished.connect(self._done)
        self._fade_out_anim.start()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()

        # subtle grid
        if self._phase >= 2:
            grid_pen = QPen(QColor(255, 255, 255, 10), 1)
            p.setPen(grid_pen)
            step = 72
            for x in range(0, rect.width(), step):
                p.drawLine(x, 0, x, rect.height())
            for y in range(0, rect.height(), step):
                p.drawLine(0, y, rect.width(), y)

        # scan beam
        if self._phase >= 2:
            y = int(self._beam)
            grad = QLinearGradient(0, y - 120, 0, y + 120)
            grad.setColorAt(0.0, QColor(120, 210, 255, 0))
            grad.setColorAt(0.48, QColor(120, 210, 255, 38))
            grad.setColorAt(0.50, QColor(255, 255, 255, 120))
            grad.setColorAt(0.52, QColor(120, 210, 255, 38))
            grad.setColorAt(1.0, QColor(120, 210, 255, 0))
            p.fillRect(QRectF(0, y - 120, rect.width(), 240), grad)

        # welcome / greeting texts
        text_color = QColor(255, 255, 255, 245)
        sub_color = QColor(245, 245, 245, 190)

        if self._phase == 0:
            title_font = QFont("Segoe UI", 70, QFont.Weight.Black)
            title_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
            p.setPen(text_color)
            p.setFont(title_font)
            p.drawText(rect.adjusted(0, -60, 0, 0), Qt.AlignmentFlag.AlignCenter, f"WELCOME, {self._device_name}")
        else:
            # reactor core
            cx, cy = rect.width() / 2, rect.height() / 2 - 18
            scale = self._zoom
            outer_r = 170 * scale
            core_r = 72 * scale

            for i in range(8):
                ring_r = outer_r + i * (14 * scale)
                alpha = max(8, 60 - i * 6)
                p.setPen(QPen(QColor(255, 255, 255, alpha), max(1.0, 1.8 * scale)))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QRectF(cx - ring_r, cy - ring_r, ring_r * 2, ring_r * 2))

            # rotating ring accents
            p.save()
            p.translate(cx, cy)
            p.rotate(self._rotation)
            for i in range(20):
                ang = (360 / 20) * i
                p.save()
                p.rotate(ang)
                p.setPen(QPen(QColor(255, 255, 255, 125), max(1.2, 1.5 * scale)))
                p.drawLine(QPointF(0, -outer_r - 4 * scale), QPointF(0, -outer_r + 16 * scale))
                p.restore()
            p.restore()

            # particles
            for pt in self._particles:
                px = pt["x"]
                py = pt["y"]
                if 0 <= px <= rect.width() and 0 <= py <= rect.height():
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(QColor(255, 255, 255, int(pt["a"])))
                    p.drawEllipse(QRectF(px, py, pt["s"], pt["s"]))

            # core glow
            glow = QRadialGradient(cx, cy, outer_r * 0.98)
            glow.setColorAt(0.0, QColor(20, 80, 140, 240))
            glow.setColorAt(0.45, QColor(10, 35, 60, 220))
            glow.setColorAt(0.7, QColor(255, 255, 255, 40))
            glow.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(glow)
            p.drawEllipse(QRectF(cx - outer_r * 0.72, cy - outer_r * 0.72, outer_r * 1.44, outer_r * 1.44))

            # inner core
            core_grad = QRadialGradient(cx, cy, core_r * 2.2)
            core_grad.setColorAt(0.0, QColor(60, 160, 255, 200))
            core_grad.setColorAt(0.35, QColor(20, 70, 130, 235))
            core_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(core_grad)
            p.drawEllipse(QRectF(cx - core_r * 2.0, cy - core_r * 2.0, core_r * 4.0, core_r * 4.0))

            # central label
            p.setPen(QColor(255, 255, 255, 220))
            p.setFont(QFont("Segoe UI", int(28 * scale), QFont.Weight.Bold))
            p.drawText(QRectF(cx - 160 * scale, cy - 40 * scale, 320 * scale, 80 * scale), Qt.AlignmentFlag.AlignCenter, "BRAHMA")

            # phase text
            if self._phase in {1, 2, 3}:
                p.setPen(text_color)
                p.setFont(QFont("Segoe UI", 26 if self._phase != 3 else 30, QFont.Weight.Bold))
                p.drawText(QRectF(0, cy + 168 * scale, rect.width(), 50), Qt.AlignmentFlag.AlignCenter, self._phase_text)
                if self._sub_text:
                    p.setPen(sub_color)
                    p.setFont(QFont("Segoe UI", 12))
                    if self._phase == 2:
                        p.drawText(QRectF(rect.width() * 0.16, cy + 220 * scale, rect.width() * 0.68, 60),
                                   Qt.AlignmentFlag.AlignCenter, self._sub_text)
                    else:
                        p.drawText(QRectF(0, cy + 214 * scale, rect.width(), 40), Qt.AlignmentFlag.AlignCenter, self._sub_text)

            # phase 2 info cards
            if self._phase >= 2:
                info_y = int(cy + 276 * scale)
                card_w = min(200, int(rect.width() * 0.18))
                gap = 16
                total = card_w * 4 + gap * 3
                start_x = int((rect.width() - total) / 2)
                info = [("CPU READY", 0), ("MEMORY READY", 1), ("NETWORK ONLINE", 2), ("AI CORE ONLINE", 3)]
                for i, (txt, _) in enumerate(info):
                    x = start_x + i * (card_w + gap)
                    rr = QRectF(x, info_y, card_w, 46)
                    p.setPen(QPen(QColor(255, 255, 255, 40), 1))
                    p.setBrush(QColor(10, 10, 10, 170))
                    p.drawRoundedRect(rr, 12, 12)
                    p.setPen(QColor(255, 255, 255, 230))
                    p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                    p.drawText(rr.adjusted(12, 0, -12, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, txt)

            # greeting phase
            if self._phase == 3:
                greeting_font = QFont("Segoe UI", 32, QFont.Weight.Bold)
                p.setPen(QColor(255, 255, 255, 245))
                p.setFont(greeting_font)
                p.drawText(QRectF(0, cy + 150 * scale, rect.width(), 48), Qt.AlignmentFlag.AlignCenter, self._phase_text)
                p.setPen(QColor(220, 220, 220, 200))
                p.setFont(QFont("Segoe UI", 14))
                p.drawText(QRectF(0, cy + 203 * scale, rect.width(), 36), Qt.AlignmentFlag.AlignCenter, "Brahma Lite is ready.")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._skip()
            return
        super().keyPressEvent(event)


class IncomingAlertDialog(QDialog):
    decision = pyqtSignal(str)

    def __init__(self, event: dict, parent=None):
        super().__init__(parent)
        self._event = event or {}
        self._kind = (self._event.get("kind") or "message").strip().lower()
        self._app = (self._event.get("app") or "App").strip()
        self._title = (self._event.get("title") or "").strip()
        self._preview = (self._event.get("preview") or "").strip()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setObjectName("IncomingAlertDialog")
        self.setMinimumWidth(360)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        frame = QFrame()
        frame.setObjectName("IncomingAlertFrame")
        frame.setStyleSheet(f"""
            QFrame#IncomingAlertFrame {{
                background: rgba(8, 8, 8, 245);
                border: 1px solid {C.BORDER_B};
                border-radius: 16px;
            }}
        """)
        root.addWidget(frame)

        lay = QVBoxLayout(frame)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)

        heading = QLabel("Incoming Call" if self._kind == "call" else "Incoming Message")
        heading.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        heading.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        lay.addWidget(heading)

        app_lbl = QLabel(f"From {self._app}")
        app_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        app_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        lay.addWidget(app_lbl)

        body = self._preview or self._title or "A notification was detected."
        body_lbl = QLabel(body)
        body_lbl.setWordWrap(True)
        body_lbl.setFont(QFont("Segoe UI", 10))
        body_lbl.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        lay.addWidget(body_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        def _btn(text: str, *, primary: bool = False, danger: bool = False) -> QPushButton:
            btn = QPushButton(text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(34)
            btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            fg = C.WHITE
            border = C.BORDER_B if primary else C.BORDER
            bg = "rgba(255,255,255,0.10)" if primary else "rgba(14,14,14,235)"
            if danger:
                border = C.RED
                bg = "rgba(60,10,10,235)"
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {bg};
                    color: {fg};
                    border: 1px solid {border};
                    border-radius: 11px;
                    padding: 0 12px;
                }}
                QPushButton:hover {{
                    background: rgba(255,255,255,0.14);
                    border: 1px solid {C.WHITE};
                }}
            """)
            return btn

        if self._kind == "call":
            self._accept_btn = _btn("Pick up", primary=True)
            self._ignore_btn = _btn("Ignore")
            self._cut_btn = _btn("Cut call", danger=True)
            self._x_btn = _btn("X")
            self._accept_btn.clicked.connect(lambda: self._choose("accept"))
            self._ignore_btn.clicked.connect(lambda: self._choose("ignore"))
            self._cut_btn.clicked.connect(lambda: self._choose("cut"))
            self._x_btn.clicked.connect(lambda: self._choose("noop"))
            for btn in (self._accept_btn, self._ignore_btn, self._cut_btn, self._x_btn):
                btn_row.addWidget(btn)
        else:
            self._hear_btn = _btn("Hear it", primary=True)
            self._ignore_btn = _btn("Ignore")
            self._x_btn = _btn("X")
            self._hear_btn.clicked.connect(lambda: self._choose("hear"))
            self._ignore_btn.clicked.connect(lambda: self._choose("ignore"))
            self._x_btn.clicked.connect(lambda: self._choose("noop"))
            btn_row.addWidget(self._hear_btn)
            btn_row.addWidget(self._ignore_btn)
            btn_row.addWidget(self._x_btn)

        lay.addLayout(btn_row)

    def _choose(self, decision: str):
        self.decision.emit(decision)
        self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._choose("ignore")
            return
        super().keyPressEvent(event)


class MeetingOverlay(QWidget):
    stop_requested = pyqtSignal()
    minimize_requested = pyqtSignal()
    close_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setMouseTracking(True)
        self._expanded_height = 142
        self._collapsed_height = 58
        self._collapsed = False
        self.setFixedHeight(self._expanded_height)
        self.setStyleSheet("background: transparent;")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background: rgba(5, 5, 5, 232);
                border: 1px solid {C.BORDER_B};
                border-radius: 18px;
            }}
        """)
        root.addWidget(frame)

        lay = QVBoxLayout(frame)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(10)

        self._badge = QLabel("MEETING MODE")
        self._badge.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._badge.setStyleSheet(
            f"color: {C.WHITE}; background: rgba(255,255,255,0.06); border: 1px solid {C.BORDER_B}; border-radius: 10px; padding: 4px 10px;"
        )
        top.addWidget(self._badge)

        self._title = QLabel("Watching the meeting")
        self._title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._title.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        top.addWidget(self._title)
        top.addStretch()

        self._min_btn = QPushButton("-")
        self._min_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._min_btn.setFixedSize(28, 28)
        self._min_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._min_btn.setToolTip("Minimize meeting bar")
        self._min_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.06);
                color: {C.WHITE};
                border: 1px solid {C.BORDER_B};
                border-radius: 9px;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.10);
                border: 1px solid {C.WHITE};
            }}
        """)
        self._min_btn.clicked.connect(self._toggle_collapsed)
        top.addWidget(self._min_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._stop_btn.setFixedHeight(28)
        self._stop_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._stop_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.06);
                color: {C.WHITE};
                border: 1px solid {C.BORDER_B};
                border-radius: 9px;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.10);
                border: 1px solid {C.WHITE};
            }}
        """)
        self._stop_btn.clicked.connect(self.stop_requested.emit)
        top.addWidget(self._stop_btn)

        self._close_btn = QPushButton("x")
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setFixedSize(28, 28)
        self._close_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._close_btn.setToolTip("Close meeting bar")
        self._close_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.06);
                color: {C.WHITE};
                border: 1px solid {C.BORDER_B};
                border-radius: 9px;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.10);
                border: 1px solid {C.WHITE};
            }}
        """)
        self._close_btn.clicked.connect(self.close_requested.emit)
        top.addWidget(self._close_btn)
        lay.addLayout(top)

        self._summary = QLabel("Waiting for a meeting to start...")
        self._summary.setWordWrap(True)
        self._summary.setFont(QFont("Segoe UI", 10))
        self._summary.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        lay.addWidget(self._summary)

        self._speech = QLabel("They said: nothing yet.")
        self._speech.setWordWrap(True)
        self._speech.setFont(QFont("Segoe UI", 10))
        self._speech.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        lay.addWidget(self._speech)

        self._answer = QLabel("Brahma will show the live answer here.")
        self._answer.setWordWrap(True)
        self._answer.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._answer.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        lay.addWidget(self._answer)

        self._apply_collapsed_state(False)

    def set_content(self, title: str, summary: str, answer: str, active: bool = True, speech: str = ""):
        self._title.setText(title or "Watching the meeting")
        self._summary.setText(summary or "Watching the meeting screen.")
        self._speech.setText(f"They said: {speech or 'nothing yet.'}")
        self._answer.setText(answer or "No question detected yet.")
        self._badge.setText("MEETING LIVE" if active else "MEETING MODE")

    def _apply_collapsed_state(self, collapsed: bool):
        self._collapsed = bool(collapsed)
        for widget in (self._summary, self._speech, self._answer):
            widget.setVisible(not self._collapsed)
        self._min_btn.setText("?" if self._collapsed else "-")
        self._min_btn.setToolTip("Restore meeting bar" if self._collapsed else "Minimize meeting bar")
        self.setFixedHeight(self._collapsed_height if self._collapsed else self._expanded_height)

    def set_collapsed(self, collapsed: bool):
        self._apply_collapsed_state(collapsed)

    def is_collapsed(self) -> bool:
        return self._collapsed

    def _toggle_collapsed(self):
        self.minimize_requested.emit()


class FloatingLauncher(QWidget):
    single_clicked = pyqtSignal()
    double_clicked = pyqtSignal()
    action_requested = pyqtSignal(str)
    position_changed = pyqtSignal(int, int)

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(74, 74)
        self._state = "idle"
        self._status_line = "Ready"
        self._hovered = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._ring = QFrame()
        self._ring.setStyleSheet("")
        lay = QVBoxLayout(self._ring)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(0)

        lay.addWidget(_framed_logo(54, 36, bg="rgba(255,255,255,0.04)", border=C.BORDER, radius=26, inset=6))
        root.addWidget(self._ring)
        _attach_pulse_glow(self._ring, color=C.WHITE, blur_min=18.0, blur_max=34.0, alpha=135, period_ms=2300)

        self._single_timer = QTimer(self)
        self._single_timer.setSingleShot(True)
        self._single_timer.timeout.connect(self.single_clicked.emit)
        self._dragging = False
        self._drag_button = None
        self._drag_offset = QPoint(0, 0)
        self._press_pos = QPoint(0, 0)
        self._apply_state_style()

    def show_at(self, x: int | None = None, y: int | None = None):
        if x is None or y is None:
            screen = QApplication.primaryScreen().availableGeometry()
            x = screen.right() - self.width() - 18
            y = screen.bottom() - self.height() - 90
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()

    def set_state(self, state: str, detail: str | None = None):
        self._state = (state or "idle").strip().lower()
        self._status_line = (detail or self._default_status()).strip() or self._default_status()
        self._apply_state_style()

    def _default_status(self) -> str:
        return {
            "idle": "Ready",
            "listening": "Listening",
            "thinking": "Thinking...",
            "executing": "Executing task...",
            "error": "Error",
        }.get(self._state, "Ready")

    def _apply_state_style(self):
        state = self._state
        accent = {
            "idle": "#00BFFF",
            "listening": "#4ef0ff",
            "thinking": "#9fd8ff",
            "executing": "#ffb14a",
            "error": "#ff6b6b",
        }.get(state, "#00BFFF")
        glow = {
            "idle": "rgba(0,191,255,0.18)",
            "listening": "rgba(78,240,255,0.26)",
            "thinking": "rgba(159,216,255,0.26)",
            "executing": "rgba(255,177,74,0.22)",
            "error": "rgba(255,107,107,0.24)",
        }.get(state, "rgba(0,191,255,0.18)")
        self._ring.setStyleSheet(f"""
            QFrame {{
                background: rgba(4, 4, 8, 234);
                border: 1px solid {accent};
                border-radius: 37px;
            }}
            QFrame:hover {{
                border: 1px solid {accent};
            }}
        """)
        self.setToolTip(f"Brahma AI\n{self._status_line}")

    def _show_menu(self, global_pos):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: rgba(8, 8, 8, 245);
                color: {C.WHITE};
                border: 1px solid {C.BORDER_B};
                border-radius: 10px;
                padding: 6px;
            }}
            QMenu::item {{
                padding: 8px 18px;
                border-radius: 6px;
            }}
            QMenu::item:selected {{
                background: rgba(255,255,255,0.08);
            }}
        """)

        actions = [
            ("New Task", "new_task"),
            ("Voice Mode", "voice_mode"),
            ("Screen Analyzer", "screen_analyzer"),
            ("Browser Agent", "browser_agent"),
            ("Settings", "settings"),
            ("Open Workspace", "open_workspace"),
        ]
        for idx, (label, key) in enumerate(actions):
            action = QAction(label, self)
            action.triggered.connect(lambda _=False, k=key: self.action_requested.emit(k))
            menu.addAction(action)
            if idx != len(actions) - 1:
                menu.addSeparator()
        menu.exec(global_pos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self._dragging:
            self._single_timer.start(180)
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self.position_changed.emit(self.x(), self.y())
        if event.button() == Qt.MouseButton.RightButton:
            if not self._dragging:
                self._show_menu(event.globalPosition().toPoint())
            self._dragging = False
            self._drag_button = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._single_timer.stop()
            self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._press_pos = event.globalPosition().toPoint()
            self._drag_offset = self._press_pos - self.frameGeometry().topLeft()
            self._single_timer.stop()
            self._drag_button = Qt.MouseButton.LeftButton
            event.accept()
            return
        if event.button() == Qt.MouseButton.RightButton:
            self._dragging = False
            self._press_pos = event.globalPosition().toPoint()
            self._drag_offset = self._press_pos - self.frameGeometry().topLeft()
            self._single_timer.stop()
            self._drag_button = Qt.MouseButton.RightButton
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            pos = event.globalPosition().toPoint()
            if not self._dragging and (pos - self._press_pos).manhattanLength() > 6:
                self._dragging = True
            if self._dragging:
                screen = QApplication.primaryScreen().availableGeometry()
                new_pos = pos - self._drag_offset
                new_x = max(screen.left(), min(new_pos.x(), screen.right() - self.width()))
                new_y = max(screen.top(), min(new_pos.y(), screen.bottom() - self.height()))
                self.move(new_x, new_y)
                self.position_changed.emit(new_x, new_y)
            event.accept()
            return
        if event.buttons() & Qt.MouseButton.RightButton and self._drag_button == Qt.MouseButton.RightButton:
            pos = event.globalPosition().toPoint()
            if not self._dragging and (pos - self._press_pos).manhattanLength() > 6:
                self._dragging = True
            if self._dragging:
                screen = QApplication.primaryScreen().availableGeometry()
                new_pos = pos - self._drag_offset
                new_x = max(screen.left(), min(new_pos.x(), screen.right() - self.width()))
                new_y = max(screen.top(), min(new_pos.y(), screen.bottom() - self.height()))
                self.move(new_x, new_y)
                self.position_changed.emit(new_x, new_y)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def enterEvent(self, event):
        self._hovered = True
        self._apply_state_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._apply_state_style()
        super().leaveEvent(event)


class MainWindow(QMainWindow):
    _log_sig   = pyqtSignal(str)
    _state_sig = pyqtSignal(str)
    _scan_sig  = pyqtSignal(bool, str)
    _attention_sig = pyqtSignal(object)
    _meeting_sig = pyqtSignal(object)
    _task_workspace_sig = pyqtSignal(object)
    discord_config_changed = pyqtSignal(object)
    discord_status_changed = pyqtSignal(str)
    minimized = pyqtSignal()

    def __init__(self, face_path: str):
        super().__init__()
        self.setWindowFlag(Qt.WindowType.Tool, False)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setWindowIcon(self._make_window_icon())
        self.setWindowTitle("Brahma AI - Lite")
        self.setMinimumSize(_MIN_W, _MIN_H)
        self.resize(_DEFAULT_W, _DEFAULT_H)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width()  - _DEFAULT_W) // 2,
            (screen.height() - _DEFAULT_H) // 2,
        )

        self.on_text_command  = None
        self.on_attention_action = None
        self.on_chat_event = None
        self.on_remote_clicked = None
        self._muted           = False
        self._wakeword_listening = False
        self._current_file: str | None = None
        self._state = "LISTENING"
        self._left_collapsed  = False
        self._right_collapsed = False
        self._current_page = "dashboard"
        self._settings_bridge = None
        self._api_ready = False
        self._app_settings_cache: dict | None = None
        self._overlay: QWidget | None = None
        self._remote_overlay: RemoteKeyOverlay | None = None
        self._scan_overlay: ScanningOverlay | None = None
        self._incoming_alert: IncomingAlertDialog | None = None
        self._meeting_overlay: MeetingOverlay | None = None
        self._meeting_overlay_collapsed = False
        self._chat_source_queue: deque[str] = deque()

        central = BackgroundWidget(BACKGROUND_IMAGE_FILE if BACKGROUND_IMAGE_FILE.exists() else None)
        central.setStyleSheet("background: transparent;")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self._left_panel = self._build_left_panel_modern()
        body.addWidget(self._left_panel, stretch=0)
        _attach_pulse_glow(self._left_panel, color=C.PRI, blur_min=8.0, blur_max=18.0, alpha=55, period_ms=3600)

        self._center_panel = self._build_center_panel_modern(face_path)
        body.addWidget(self._center_panel, stretch=1)
        _attach_pulse_glow(self._center_panel, color=C.PRI, blur_min=6.0, blur_max=14.0, alpha=36, period_ms=4200)

        self._right_panel = self._build_right_panel_modern()
        body.addWidget(self._right_panel, stretch=0)
        _attach_pulse_glow(self._right_panel, color=C.PRI, blur_min=8.0, blur_max=18.0, alpha=55, period_ms=3900)

        root.addLayout(body, stretch=1)

        self._clock_tmr = QTimer(self)
        self._clock_tmr.timeout.connect(self._tick_clock)
        self._clock_tmr.start(1000)
        self._tick_clock()

        # Metrik gÃ¼ncelleme timer'Ä±
        self._metric_tmr = QTimer(self)
        self._metric_tmr.timeout.connect(self._update_metrics)
        self._metric_tmr.start(2000)
        self._update_metrics()

        self._log_sig.connect(self._on_log_text)
        self._state_sig.connect(self._apply_state)
        self._attention_sig.connect(self._show_attention_alert)
        self._meeting_sig.connect(self._apply_meeting_state)
        self._task_workspace_sig.connect(self._apply_task_workspace)
        self.discord_status_changed.connect(self._on_discord_status_update)

        self._ready = False
        self._card_hide_tmr = QTimer(self)
        self._card_hide_tmr.setSingleShot(True)
        self._card_hide_tmr.timeout.connect(self._hide_command_cards)

        self._ready = self._check_config()
        self._api_ready = self._ready
        if self._ready:
            self._apply_state("LISTENING")
        else:
            self._show_setup(self._load_api_defaults())
        self._scan_sig.connect(self._apply_scan_state)

        sc_mute = QShortcut(QKeySequence("F4"), self)
        sc_mute.activated.connect(self._toggle_mute)
        sc_full = QShortcut(QKeySequence("F11"), self)
        sc_full.activated.connect(self._toggle_fullscreen)
        sc_left = QShortcut(QKeySequence("Ctrl+["), self)
        sc_left.activated.connect(self._toggle_left_sidebar)
        sc_right = QShortcut(QKeySequence("Ctrl+]"), self)
        sc_right.activated.connect(self._toggle_right_sidebar)

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _load_app_settings(self) -> dict:
        if self._app_settings_cache is not None:
            return dict(self._app_settings_cache)
        settings = _default_app_settings()
        if APP_SETTINGS_FILE.exists():
            try:
                data = json.loads(APP_SETTINGS_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    settings.update({k: data.get(k, v) for k, v in settings.items()})
            except Exception:
                pass
        self._app_settings_cache = dict(settings)
        return dict(settings)

    def _save_app_settings(self, settings: dict):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        APP_SETTINGS_FILE.write_text(json.dumps(settings, indent=4), encoding="utf-8")
        self._app_settings_cache = dict(settings)

    def _startup_animation_enabled(self) -> bool:
        if platform.system() != "Windows":
            return False
        return bool(self._load_app_settings().get("startup_animation_enabled", True))

    def _set_startup_animation_enabled(self, enabled: bool) -> bool:
        try:
            settings = self._load_app_settings()
            settings["startup_animation_enabled"] = bool(enabled)
            settings["last_boot_stamp"] = _current_boot_stamp()
            self._save_app_settings(settings)
            return True
        except Exception as e:
            self._log.append_log("ERR: startup animation setting failed: %s" % e)
            return False

    def _refresh_startup_animation_button(self):
        if not hasattr(self, "_startup_anim_btn"):
            return
        if platform.system() != "Windows":
            self._startup_anim_btn.setText("Startup Animation (Windows only)")
            self._startup_anim_btn.setEnabled(False)
            return
        if self._startup_animation_enabled():
            self._startup_anim_btn.setText("Disable Startup Animation")
        else:
            self._startup_anim_btn.setText("Enable Startup Animation")

    def _toggle_startup_animation(self):
        if platform.system() != "Windows":
            return
        enabled = not self._startup_animation_enabled()
        if self._set_startup_animation_enabled(enabled):
            self._refresh_startup_animation_button()
            state = "enabled" if enabled else "disabled"
            self._log.append_log("SYS: Startup animation %s." % state)

    def _load_discord_settings(self) -> dict:
        settings = _default_discord_settings()
        if DISCORD_SETTINGS_FILE.exists():
            try:
                data = json.loads(DISCORD_SETTINGS_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    settings.update({k: data.get(k, v) for k, v in settings.items()})
            except Exception:
                pass
        if (settings.get("bot_token") or "").strip():
            settings["enabled"] = True
        return dict(settings)

    def _save_discord_settings(self, settings: dict):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        DISCORD_SETTINGS_FILE.write_text(json.dumps(settings, indent=4), encoding="utf-8")

    def _emit_discord_settings(self):
        if not hasattr(self, "_discord_token_input"):
            return
        settings = {
            "bot_token": self._discord_token_input.text().strip(),
            "enabled": bool(getattr(self, "_discord_enabled", False)),
            "channel_id": self._discord_channel_input.text().strip() if hasattr(self, "_discord_channel_input") else "",
        }
        self._save_discord_settings(settings)
        self.discord_config_changed.emit(dict(settings))
        self._refresh_discord_card()

    def _refresh_discord_card(self, note: str = ""):
        if not hasattr(self, "_discord_status_lbl"):
            return
        token = self._discord_token_input.text().strip() if hasattr(self, "_discord_token_input") else ""
        enabled = bool(getattr(self, "_discord_enabled", False))
        channel_id = self._discord_channel_input.text().strip() if hasattr(self, "_discord_channel_input") else ""
        if note:
            status = note
            color = C.PRI if "error" in note.lower() or "missing" in note.lower() else C.TEXT_MED
        elif not token:
            status = "Token required"
            color = C.PRI
        elif not channel_id:
            status = "Token saved - channel optional"
            color = C.TEXT_MED
        elif enabled:
            status = "Bot enabled"
            color = C.GREEN
        else:
            status = "Bot disabled"
            color = C.TEXT_MED
        self._discord_status_lbl.setText(status)
        self._discord_status_lbl.setStyleSheet(f"color: {color}; background: transparent;")
        if hasattr(self, "_discord_start_btn"):
            self._discord_start_btn.setText("Start Discord Bot")
        if hasattr(self, "_discord_stop_btn"):
            self._discord_stop_btn.setText("Stop Discord Bot")
        if hasattr(self, "_discord_save_btn"):
            self._discord_save_btn.setText("Save Settings")

    def _save_discord_token(self):
        if not hasattr(self, "_discord_token_input"):
            return
        token = self._discord_token_input.text().strip()
        channel_id = self._discord_channel_input.text().strip() if hasattr(self, "_discord_channel_input") else ""
        settings = self._load_discord_settings()
        settings["bot_token"] = token
        settings["channel_id"] = channel_id
        settings["enabled"] = bool(token)
        self._discord_enabled = bool(token)
        self._save_discord_settings(settings)
        self.discord_config_changed.emit(dict(settings))
        if token:
            self._log.append_log("SYS: Discord bot token saved and bot enabled.")
            self._refresh_discord_card("Token saved")
        else:
            self._log.append_log("SYS: Discord bot token cleared.")
            self._discord_enabled = False
            self._refresh_discord_card("Token required")

    def _start_discord_bot(self):
        if not hasattr(self, "_discord_token_input"):
            return
        token = self._discord_token_input.text().strip()
        channel_id = self._discord_channel_input.text().strip() if hasattr(self, "_discord_channel_input") else ""
        if not token:
            self._discord_enabled = False
            self._save_discord_token()
            return
        self._discord_enabled = True
        settings = {
            "bot_token": token,
            "enabled": True,
            "channel_id": channel_id,
        }
        self._save_discord_settings(settings)
        self.discord_config_changed.emit(dict(settings))
        self._log.append_log("SYS: Discord bot started.")
        self._refresh_discord_card()

    def _stop_discord_bot(self):
        if not hasattr(self, "_discord_token_input"):
            return
        token = self._discord_token_input.text().strip()
        channel_id = self._discord_channel_input.text().strip() if hasattr(self, "_discord_channel_input") else ""
        self._discord_enabled = False
        settings = {
            "bot_token": token,
            "enabled": False,
            "channel_id": channel_id,
        }
        self._save_discord_settings(settings)
        self.discord_config_changed.emit(dict(settings))
        self._log.append_log("SYS: Discord bot stopped.")
        self._refresh_discord_card()

    def _load_api_defaults(self) -> dict:
        if not API_FILE.exists():
            return {
                "gemini_api_key": "",
                "openrouter_api_key": "",
                "os_system": platform.system(),
            }
        try:
            data = json.loads(API_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {
            "gemini_api_key": "",
            "openrouter_api_key": "",
            "os_system": platform.system(),
        }

    def _startup_enabled(self) -> bool:
        if platform.system() != "Windows":
            return False
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                _startup_registry_key(),
                0,
                winreg.KEY_READ | winreg.KEY_WRITE,
            ) as key:
                try:
                    value, _ = winreg.QueryValueEx(key, "Brahma AI - Lite")
                    run_value = _startup_run_value()
                    if value != run_value:
                        winreg.SetValueEx(key, "Brahma AI - Lite", 0, winreg.REG_SZ, run_value)
                    return bool(value)
                except FileNotFoundError:
                    return False
        except Exception:
            return False

    def _set_startup_enabled(self, enabled: bool) -> bool:
        if platform.system() != "Windows":
            return False
        run_value = _startup_run_value()
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _startup_registry_key()) as key:
                if enabled:
                    winreg.SetValueEx(key, "Brahma AI - Lite", 0, winreg.REG_SZ, run_value)
                else:
                    try:
                        winreg.DeleteValue(key, "Brahma AI - Lite")
                    except FileNotFoundError:
                        pass
            return True
        except Exception as e:
            self._log.append_log(f"ERR: startup setting failed: {e}")
            return False

    def _refresh_startup_button(self):
        if not hasattr(self, "_startup_btn"):
            return
        if platform.system() != "Windows":
            self._startup_btn.setText("Start on Startup (Windows only)")
            self._startup_btn.setEnabled(False)
            return
        if self._startup_enabled():
            self._startup_btn.setText("Start on Startup: ON")
        else:
            self._startup_btn.setText("Start on Startup: OFF")

    def _toggle_startup(self):
        if platform.system() != "Windows":
            return
        enabled = not self._startup_enabled()
        if self._set_startup_enabled(enabled):
            self._refresh_startup_button()
            state = "enabled" if enabled else "disabled"
            self._log.append_log(f"SYS: Windows startup {state}.")

    def _toggle_left_sidebar(self):
        self._left_collapsed = not self._left_collapsed
        self._apply_sidebar_state()

    def _toggle_right_sidebar(self):
        self._right_collapsed = not self._right_collapsed
        self._apply_sidebar_state()

    def _apply_sidebar_state(self):
        if hasattr(self, "_left_content"):
            self._left_content.setVisible(not self._left_collapsed)
            if hasattr(self, "_left_panel"):
                self._left_panel.setFixedWidth(56 if self._left_collapsed else _LEFT_W)
            if hasattr(self, "_left_toggle_btn"):
                self._left_toggle_btn.setText(">" if self._left_collapsed else "<")
                self._left_toggle_btn.setToolTip("Expand left sidebar" if self._left_collapsed else "Collapse left sidebar")
        if hasattr(self, "_right_content"):
            self._right_content.setVisible(not self._right_collapsed)
        if hasattr(self, "_right_stack"):
            self._right_stack.setVisible(not self._right_collapsed)
            if hasattr(self, "_right_panel"):
                self._right_panel.setFixedWidth(56 if self._right_collapsed else _RIGHT_W)
            if hasattr(self, "_right_toggle_btn"):
                self._right_toggle_btn.setText("<" if self._right_collapsed else ">")
                self._right_toggle_btn.setToolTip("Expand right sidebar" if self._right_collapsed else "Collapse right sidebar")
        if hasattr(self, "_center_panel"):
            self._center_panel.update()

    def set_settings_bridge(self, bridge):
        self._settings_bridge = bridge
        if hasattr(self, "_settings_page") and hasattr(self._settings_page, "set_controller"):
            self._settings_page.set_controller(bridge)
        if hasattr(self, "_settings_sidebar") and hasattr(self._settings_sidebar, "set_controller"):
            self._settings_sidebar.set_controller(bridge)
        self._set_page(self._current_page)

    def _set_page(self, page: str):
        self._current_page = page
        if hasattr(self, "_center_stack") and isinstance(self._center_stack, QStackedWidget):
            index = {"dashboard": 0, "home": 1, "settings": 2}.get(page, 0)
            self._center_stack.setCurrentIndex(index)
        if hasattr(self, "_right_panel"):
            self._right_panel.setVisible(page == "dashboard")
        if hasattr(self, "_right_stack") and isinstance(self._right_stack, QStackedWidget):
            self._right_stack.setCurrentIndex({"dashboard": 0, "settings": 1, "home": 2}.get(page, 2))
            self._right_stack.setVisible(page == "dashboard")
        if self._settings_bridge and hasattr(self._settings_bridge, "set_dashboard_page"):
            try:
                self._settings_bridge.set_dashboard_page(page == "dashboard")
            except Exception:
                pass
        if page == "settings" and hasattr(self, "_settings_page"):
            try:
                self._settings_page.refresh()
            except Exception:
                pass
        if page == "settings" and hasattr(self, "_settings_sidebar"):
            try:
                self._settings_sidebar.refresh()
            except Exception:
                pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._overlay and self._overlay.isVisible():
            size = self._overlay.sizeHint()
            ow = max(360, size.width() or self._overlay.width() or 460)
            oh = max(320, size.height() or self._overlay.height() or 390)
            cw = self.centralWidget()
            self._overlay.setGeometry(
                (cw.width()  - ow) // 2,
                (cw.height() - oh) // 2,
                ow, oh,
            )

    def _update_metrics(self):
        if not hasattr(self, "_bar_cpu"):
            return
        snap = _metrics.snapshot()

        # CPU
        cpu = snap["cpu"]
        self._bar_cpu.set_value(cpu, f"{cpu:.0f}%")
        if hasattr(self, "_stat_cpu"):
            cpu_cores = psutil.cpu_count(logical=False) or psutil.cpu_count(logical=True) or 0
            cpu_threads = psutil.cpu_count(logical=True) or cpu_cores
            self._stat_cpu.set_value(
                f"{cpu:.0f}%",
                int(cpu),
                f"{cpu_threads} threads / {cpu_cores or cpu_threads} cores",
            )

        # MEM
        mem = snap["mem"]
        self._bar_mem.set_value(mem, f"{mem:.0f}%")
        if hasattr(self, "_stat_mem"):
            vm = psutil.virtual_memory()
            used_gb = vm.used / (1024**3)
            total_gb = vm.total / (1024**3)
            self._stat_mem.set_value(
                f"{mem:.0f}%",
                int(mem),
                f"{used_gb:.1f} GB / {total_gb:.1f} GB used",
            )

        # NET
        net = snap["net"]
        if net < 1.0:
            net_str = f"{net*1024:.0f}KB/s"
        else:
            net_str = f"{net:.1f}MB/s"
        net_pct = min(100, net * 10)  # 10 MB/s = %100
        self._bar_net.set_value(net_pct, net_str)
        if hasattr(self, "_stat_net"):
            self._stat_net.set_value(
                net_str if net >= 1 else "ONLINE",
                int(net_pct),
                _active_net_label(),
            )

        # GPU
        gpu = snap["gpu"]
        if gpu >= 0:
            self._bar_gpu.set_value(gpu, f"{gpu:.0f}%")
        else:
            self._bar_gpu.set_value(0, "N/A")

        # TMP
        tmp = snap["tmp"]
        if tmp >= 0:
            tmp_pct = min(100, (tmp / 100) * 100)
            self._bar_tmp.set_value(tmp_pct, f"{tmp:.0f}Â°C")
        else:
            self._bar_tmp.set_value(0, "N/A")
        if hasattr(self, "_stat_cam"):
            cam_on = _camera_available()
            self._stat_cam.set_value(
                "ON" if cam_on else "OFF",
                100 if cam_on else 0,
                "Webcam detected" if cam_on else "No camera found",
            )

        try:
            boot_t  = psutil.boot_time()
            elapsed = time.time() - boot_t
            h = int(elapsed // 3600)
            m = int((elapsed % 3600) // 60)
            self._uptime_lbl.setText(f"UP  {h:02d}:{m:02d}")
        except Exception:
            self._uptime_lbl.setText("UP  --:--")

        try:
            proc_count = len(psutil.pids())
            self._proc_lbl.setText(f"PROC  {proc_count}")
        except Exception:
            self._proc_lbl.setText("PROC  --")


    def _build_header(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(54)
        w.setStyleSheet(f"background: {C.DARK}; border-bottom: 1px solid {C.BORDER_B};")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(16, 0, 16, 0)

        def _badge(txt, color=C.TEXT_MED):
            l = QLabel(txt)
            l.setFont(QFont("Courier New", 8))
            l.setStyleSheet(f"color: {color}; background: transparent;")
            return l

        lay.addWidget(_badge("BRAHMA AI - LITE", C.PRI_DIM))
        lay.addStretch()

        mid = QVBoxLayout(); mid.setSpacing(1)
        title = QLabel("BRAHMA AI")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Courier New", 17, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        mid.addWidget(title)
        sub = QLabel("Lite Edition by Suryaansh Tiwari")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setFont(QFont("Courier New", 7))
        sub.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent;")
        mid.addWidget(sub)
        lay.addLayout(mid)
        lay.addStretch()

        right_col = QVBoxLayout(); right_col.setSpacing(2)
        self._clock_lbl = QLabel("00:00:00")
        self._clock_lbl.setFont(QFont("Courier New", 14, QFont.Weight.Bold))
        self._clock_lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        self._clock_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._clock_lbl)
        self._date_lbl = QLabel("")
        self._date_lbl.setFont(QFont("Courier New", 7))
        self._date_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        self._date_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._date_lbl)
        lay.addLayout(right_col)
        return w

    def _tick_clock(self):
        if hasattr(self, "_clock_lbl") and self._clock_lbl is not None:
            self._clock_lbl.setText(time.strftime("%H:%M"))
        if hasattr(self, "_date_lbl") and self._date_lbl is not None:
            self._date_lbl.setText(time.strftime("%A • %d %b"))
        if hasattr(self, "_core_lbl") and self._core_lbl is not None:
            hour = time.localtime().tm_hour
            if hour < 12:
                greeting = "Good Morning"
            elif hour < 18:
                greeting = "Good Afternoon"
            else:
                greeting = "Good Evening"
            name = os.getenv("USERNAME") or os.getenv("USER") or "Suryaansh"
            self._core_lbl.setText(f"{greeting}, {name}")
        if hasattr(self, "_core_sub_lbl") and self._core_sub_lbl is not None:
            self._core_sub_lbl.setText("Ready to assist.")
        if hasattr(self, "_core_status_lbl") and self._core_status_lbl is not None:
            self._core_status_lbl.setText("Brahma is ready. Gemini 2.5 Flash · OpenRouter · Voice Connected · Memory Enabled")
        if hasattr(self, "_cpu_lbl") and self._cpu_lbl is not None:
            self._cpu_lbl.setText(f"CPU {int(psutil.cpu_percent(interval=None))}%")
        if hasattr(self, "_ram_lbl") and self._ram_lbl is not None:
            self._ram_lbl.setText(f"RAM {int(psutil.virtual_memory().percent)}%")

    def _make_window_icon(self) -> QIcon:
        return _logo_icon()

    def _build_left_panel(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(_LEFT_W)
        w.setStyleSheet(f"background: {C.DARK}; border-right: 1px solid {C.BORDER};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 10, 8, 10)
        lay.setSpacing(6)

        hdr = QLabel("â—ˆ SYS MONITOR")
        hdr.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; "
                          f"border-bottom: 1px solid {C.BORDER}; padding-bottom: 4px;")
        lay.addWidget(hdr)
        lay.addSpacing(2)

        self._bar_cpu = MetricBar("CPU", C.PRI)
        self._bar_mem = MetricBar("MEM", C.ACC2)
        self._bar_net = MetricBar("NET", C.GREEN)
        self._bar_gpu = MetricBar("GPU", C.ACC)
        self._bar_tmp = MetricBar("TMP", "#ff6688")

        for bar in [self._bar_cpu, self._bar_mem, self._bar_net,
                    self._bar_gpu, self._bar_tmp]:
            lay.addWidget(bar)

        lay.addSpacing(4)

        info_panel = QWidget()
        info_panel.setStyleSheet(
            f"background: {C.PANEL2}; border: 1px solid {C.BORDER}; border-radius: 4px;"
        )
        ip_lay = QVBoxLayout(info_panel)
        ip_lay.setContentsMargins(6, 5, 6, 5)
        ip_lay.setSpacing(3)

        self._uptime_lbl = QLabel("UP  --:--")
        self._uptime_lbl.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._uptime_lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent; border: none;")
        ip_lay.addWidget(self._uptime_lbl)

        self._proc_lbl = QLabel("PROC  --")
        self._proc_lbl.setFont(QFont("Courier New", 8))
        self._proc_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent; border: none;")
        ip_lay.addWidget(self._proc_lbl)

        os_name = {"Windows": "WIN", "Darwin": "macOS", "Linux": "LINUX"}.get(_OS, _OS.upper())
        os_lbl = QLabel(f"OS  {os_name}")
        os_lbl.setFont(QFont("Courier New", 8))
        os_lbl.setStyleSheet(f"color: {C.ACC2}; background: transparent; border: none;")
        ip_lay.addWidget(os_lbl)

        lay.addWidget(info_panel)
        lay.addStretch()

        for txt, col in [
            ("AI CORE\nACTIVE",     C.GREEN),
            ("SEC\nCLEARED",        C.PRI),
            ("PROTOCOL\nXXXVIII",   C.TEXT_DIM),
        ]:
            lbl = QLabel(txt)
            lbl.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                f"color: {col}; background: {C.PANEL2};"
                f"border: 1px solid {C.BORDER_A}; border-radius: 3px; padding: 4px;"
            )
            lay.addWidget(lbl)

        return w
    def _build_right_panel(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(_RIGHT_W)
        w.setStyleSheet(f"background: {C.DARK}; border-left: 1px solid {C.BORDER};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        def _sec(txt):
            l = QLabel(f"â-¸ {txt}")
            l.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            l.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
            return l

        lay.addWidget(_sec("ACTIVITY LOG"))
        self._log = LogWidget()
        lay.addWidget(self._log, stretch=1)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(sep)

        lay.addWidget(_sec("FILE UPLOAD"))
        self._drop_zone = FileDropZone()
        self._drop_zone.file_selected.connect(self._on_file_selected)
        lay.addWidget(self._drop_zone)

        self._file_hint = QLabel("No file loaded â€” drop or click above to upload")
        self._file_hint.setFont(QFont("Courier New", 7))
        self._file_hint.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        self._file_hint.setWordWrap(True)
        lay.addWidget(self._file_hint)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(sep2)

        lay.addWidget(_sec("COMMAND INPUT"))
        lay.addLayout(self._build_input_row())

        self._mute_btn = QPushButton("ðŸŽ™  MICROPHONE ACTIVE")
        self._mute_btn.setFixedHeight(30)
        self._mute_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._mute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mute_btn.clicked.connect(self._toggle_mute)
        self._style_mute_btn()
        lay.addWidget(self._mute_btn)

        fs_btn = QPushButton("â›¶  FULLSCREEN  [F11]")
        fs_btn.setFixedHeight(26)
        fs_btn.setFont(QFont("Courier New", 7))
        fs_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        fs_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px;
            }}
            QPushButton:hover {{
                color: {C.PRI}; border: 1px solid {C.BORDER_B};
            }}
        """)
        fs_btn.clicked.connect(self._toggle_fullscreen)
        lay.addWidget(fs_btn)

        return w

    def _build_input_row(self) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(5)
        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a command or questionâ€¦")
        self._input.setFont(QFont("Courier New", 9))
        self._input.setFixedHeight(30)
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: #000d14; color: {C.WHITE};
                border: 1px solid {C.BORDER}; border-radius: 3px; padding: 3px 7px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
        """)
        self._input.returnPressed.connect(self._send)
        row.addWidget(self._input)

        send = QPushButton("â-¸")
        send.setFixedSize(30, 30)
        send.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        send.setCursor(Qt.CursorShape.PointingHandCursor)
        send.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL}; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 3px;
            }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border: 1px solid {C.PRI}; }}
        """)
        send.clicked.connect(self._send)
        row.addWidget(send)
        return row

    def _build_footer(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(22)
        w.setStyleSheet(f"background: {C.DARK}; border-top: 1px solid {C.BORDER};")
        lay = QHBoxLayout(w); lay.setContentsMargins(14, 0, 14, 0)

        def _fl(txt, color=C.TEXT_MED):
            l = QLabel(txt); l.setFont(QFont("Courier New", 7))
            l.setStyleSheet(f"color: {color}; background: transparent;")
            return l

        lay.addWidget(_fl("[F4] Mute  Â·  [F11] Fullscreen"))
        lay.addStretch()
        lay.addWidget(_fl("Suryaansh Tiwari  Â·  Brahma AI - Lite  Â·  Open Source"))
        lay.addStretch()
        lay.addWidget(_fl("Â© STARK INDUSTRIES", C.PRI_DIM))
        return w

    def _on_file_selected(self, path: str):
        self._current_file = path
        p = Path(path)
        cat = _file_category(p)
        icon, _ = _FILE_ICONS.get(cat, _FILE_ICONS["unknown"])
        size = _fmt_size(p.stat().st_size)
        if hasattr(self, "_file_chip") and self._file_chip:
            self._file_chip.setText(f"Attached: {icon} {p.name}  â€¢  {size}")
        self._log.append_log(f"FILE: {p.name} ({size}) loaded")
        if self.on_text_command:
            msg = (
                f"[FILE_UPLOADED] path={path} | name={p.name} | "
                f"type={p.suffix.lstrip('.') } | size={size} | "
                f"Briefly tell the user you can see the file '{p.name}' "
                f"({size}) has been uploaded and ask what they'd like to do with it."
            )
            threading.Thread(target=self.on_text_command, args=(msg,), daemon=True).start()

    def _browse_attachment(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Attach a file to Brahma", str(Path.home()),
            "All Files (*.*);;"
            "Images (*.jpg *.jpeg *.png *.gif *.webp *.bmp *.svg);;"
            "Documents (*.pdf *.docx *.txt *.md *.pptx);;"
            "Data (*.csv *.xlsx *.json *.xml);;"
            "Code (*.py *.js *.ts *.html *.css *.java *.cpp *.go);;"
            "Audio (*.mp3 *.wav *.ogg *.m4a *.aac *.flac);;"
            "Video (*.mp4 *.avi *.mov *.mkv *.wmv *.webm);;"
            "Archives (*.zip *.rar *.tar *.gz *.7z)",
        )
        if path:
            self._on_file_selected(path)

    def _toggle_mute(self):
        self._muted = not self._muted
        self._wakeword_listening = self._muted
        self.hud.muted = self._muted
        self._style_mute_btn()
        if self._muted:
            self._apply_state("MUTED")
            self._log.append_log("SYS: Microphone muted.")
        else:
            self._apply_state("LISTENING")
            self._log.append_log("SYS: Microphone active.")

    def set_muted_state(self, muted: bool, *, wakeword: bool = False):
        muted = bool(muted)
        if muted == self._muted and not wakeword:
            return
        self._muted = muted
        self.hud.muted = self._muted
        self._wakeword_listening = bool(muted)
        self._style_mute_btn()
        if self._muted:
            self._apply_state("MUTED")
            self._log.append_log("SYS: Microphone muted.")
        else:
            self._apply_state("LISTENING")
            self._log.append_log("SYS: Microphone active.")

    def _style_mute_btn(self):
        if not hasattr(self, "_mute_btn") or self._mute_btn is None:
            return
        if self._muted:
            self._mute_btn.setText("Muted")
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{
                    background: #1a1010; color: {C.RED};
                    border: 1px solid {C.RED}; border-radius: 16px;
                }}
            """)
        else:
            self._mute_btn.setText("Mic")
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(16,16,16,235); color: {C.WHITE};
                    border: 1px solid {C.BORDER_B}; border-radius: 16px;
                }}
                QPushButton:hover {{ border: 1px solid {C.WHITE}; }}
            """)

    def _send(self):
        txt = self._input.text().strip()
        if not txt:
            return
        self._input.clear()
        self.submit_command(txt)

    def submit_command(self, txt: str, source: str = "local"):
        txt = (txt or "").strip()
        if not txt:
            return
        self._chat_source_queue.append(source or "local")
        if hasattr(self, "_command_card"):
            preview = txt[:60] + ("…" if len(txt) > 60 else "")
            self._command_card.set_body(preview)
            self._command_card.show()
        if hasattr(self, "_result_card"):
            self._result_card.set_body("Waiting for reply...")
            self._result_card.show()
        self._restart_card_hide_timer()
        self._log.append_log(f"You: {txt}")
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(txt, source or "local"), daemon=True).start()

    def _on_log_text(self, text: str):
        self._log.append_log(text)
        raw = (text or "").strip()
        low = raw.lower()
        if hasattr(self, "_result_card") and low.startswith("you:"):
            user_msg = raw.split(":", 1)[1].strip()
            source = self._chat_source_queue[0] if self._chat_source_queue else "local"
            if self.on_chat_event and user_msg:
                try:
                    self.on_chat_event({"role": "user", "text": user_msg, "source": source})
                except Exception:
                    pass
        if hasattr(self, "_result_card") and low.startswith("brahma ai:"):
            reply = raw.split(":", 1)[1].strip()
            self._result_card.set_body(reply[:80] + ("…" if len(reply) > 80 else ""))
            self._result_card.show()
            self._restart_card_hide_timer()
            source = self._chat_source_queue[0] if self._chat_source_queue else "local"
            if self.on_chat_event and reply:
                try:
                    self.on_chat_event({"role": "assistant", "text": reply, "source": source})
                except Exception:
                    pass
            if self._chat_source_queue:
                self._chat_source_queue.popleft()
        elif hasattr(self, "_result_card") and low.startswith("err:"):
            self._result_card.set_body(raw.split(":", 1)[1].strip())
            self._result_card.show()
            self._restart_card_hide_timer()
            source = self._chat_source_queue[0] if self._chat_source_queue else "local"
            if self.on_chat_event:
                try:
                    self.on_chat_event({"role": "system", "text": raw.split(":", 1)[1].strip(), "source": source})
                except Exception:
                    pass
            if self._chat_source_queue:
                self._chat_source_queue.popleft()

    def _restart_card_hide_timer(self):
        if hasattr(self, "_card_hide_tmr"):
            self._card_hide_tmr.start(5000)

    def _hide_command_cards(self):
        if hasattr(self, "_command_card"):
            self._command_card.hide()
        if hasattr(self, "_result_card"):
            self._result_card.hide()

    def show_app(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _show_remote_connect(self):
        if not self.on_remote_clicked:
            self._log_sig.emit("ERR: Mobile remote is not ready yet.")
            return
        result = self.on_remote_clicked()
        if not result:
            self._log_sig.emit("ERR: Mobile remote could not start. Install dashboard dependencies and try again.")
            return
        url = result[0]
        key = result[1]
        auto = result[2] if len(result) >= 3 else url
        manual = result[3] if len(result) >= 4 else url

        if self._remote_overlay is not None:
            try:
                self._remote_overlay.deleteLater()
            except Exception:
                pass
            self._remote_overlay = None

        overlay = RemoteKeyOverlay(url, key, auto, manual, parent=self)
        overlay.set_new_key_callback(self.on_remote_clicked)
        overlay.closed.connect(lambda: setattr(self, "_remote_overlay", None))
        self._remote_overlay = overlay
        self._position_remote_overlay()
        overlay.show()
        overlay.raise_()
        self._log_sig.emit(f"SYS: Mobile Connect ready at {manual}. Scan the QR code or enter key {key}.")

    def _position_remote_overlay(self):
        if not self._remote_overlay:
            return
        geo = self.geometry()
        x = max(16, (geo.width() - self._remote_overlay.width()) // 2)
        y = max(16, (geo.height() - self._remote_overlay.height()) // 2)
        self._remote_overlay.move(x, y)

    def notify_phone_connected(self):
        if self._remote_overlay is not None:
            self._remote_overlay.mark_connected()
        self._log_sig.emit("SYS: Phone connected to Brahma remote.")

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and self.isMinimized():
            self.minimized.emit()

    def _apply_state(self, state: str):
        self._state = state
        self.hud.state = state
        self.hud.speaking = (state == "SPEAKING")
        if hasattr(self, "_status_chip"):
            chip_text = {
                "THINKING": "● WORKING",
                "SPEAKING": "● SPEAKING",
                "MUTED":    "● MUTED",
            }.get(state, "● ONLINE")
            self._status_chip.setText(chip_text)
            color = C.PRI if state == "MUTED" else C.GREEN if state in ("LISTENING", "SPEAKING") else C.WHITE
            border = C.PRI if state in ("MUTED", "THINKING") else "rgba(255,255,255,0.12)"
            self._status_chip.setStyleSheet(
                f"color: {color}; background: rgba(11,12,16,238); border: 1px solid {border}; border-radius: 999px; padding: 7px 14px;"
            )
        if hasattr(self, "_time_status_lbl"):
            status_text = {
                "THINKING": "Working",
                "SPEAKING": "Speaking",
                "MUTED": "Muted",
            }.get(state, "Online")
            self._time_status_lbl.setText(status_text)
            self._time_status_lbl.setStyleSheet(
                f"color: {C.GREEN if state in ('LISTENING', 'SPEAKING') else C.RED if state == 'MUTED' else C.WHITE}; background: transparent;"
            )
        if hasattr(self, "_task_card"):
            if state == "THINKING":
                self._task_card.set_task("Working on it...", "Brahma is processing your request.", 72)
            elif state == "SPEAKING":
                self._task_card.set_task("Responding...", "Brahma is speaking now.", 100)
            elif state == "MUTED":
                self._task_card.set_task("Microphone muted", "Voice input is paused.", 0)
            else:
                self._task_card.set_task("Ready", "Brahma is idle and ready.", 0)
        if hasattr(self, "_result_card"):
            if state == "THINKING":
                self._result_card.set_body("Action pending")
            elif state == "SPEAKING":
                self._result_card.set_body("Speaking now")
            elif state == "MUTED":
                self._result_card.set_body("Voice muted")
            else:
                self._result_card.set_body("Action completed")

    def _check_config(self) -> bool:
        if not API_FILE.exists(): return False
        try:
            d = json.loads(API_FILE.read_text(encoding="utf-8"))
            return (bool(d.get("gemini_api_key")) and
                    bool(d.get("os_system")))
        except Exception:
            return False

    def _apply_scan_state(self, enabled: bool, text: str = ""):
        if enabled:
            if self._scan_overlay is None:
                self._scan_overlay = ScanningOverlay()
            self._scan_overlay.show_fullscreen(text or "SCANNING SCREEN", "Analyzing display...")
        else:
            if self._scan_overlay is not None:
                self._scan_overlay.hide_overlay()

    def set_scanning(self, enabled: bool, text: str = ""):
        self._scan_sig.emit(bool(enabled), text or "")

    def set_meeting_mode(self, enabled: bool, title: str = "", summary: str = "", answer: str = "", speech: str = ""):
        self._meeting_sig.emit({
            "enabled": bool(enabled),
            "title": title or "",
            "summary": summary or "",
            "answer": answer or "",
            "speech": speech or "",
        })

    def _apply_meeting_state(self, event: object):
        data = event if isinstance(event, dict) else {}
        enabled = bool(data.get("enabled"))
        title = (data.get("title") or "").strip()
        summary = (data.get("summary") or "").strip()
        answer = (data.get("answer") or "").strip()
        speech = (data.get("speech") or "").strip()

        if enabled:
            if self._meeting_overlay is None:
                self._meeting_overlay = MeetingOverlay()
                self._meeting_overlay.stop_requested.connect(self._request_stop_meeting)
                self._meeting_overlay.minimize_requested.connect(self._toggle_meeting_overlay)
                self._meeting_overlay.close_requested.connect(self._request_stop_meeting)
            self._meeting_overlay.set_content(
                title or "Meeting mode",
                summary or "Watching the meeting screen.",
                answer or "No question detected yet.",
                True,
                speech,
            )
            self._position_meeting_overlay()
            self._meeting_overlay.set_collapsed(self._meeting_overlay_collapsed)
            self._meeting_overlay.show()

    def _apply_task_workspace(self, event: object):
        data = event if isinstance(event, dict) else {}
        target = getattr(self, "_task_card", None)
        if target is None:
            return
        action = (data.get("action") or "update").strip().lower()
        if action == "start":
            target.start_workspace(
                data.get("command") or "",
                data.get("plan") or [],
                data.get("source") or "local",
            )
        elif action == "update":
            target.update_workspace(
                title=data.get("title"),
                command=data.get("command"),
                plan=data.get("plan"),
                status=data.get("status"),
                output=data.get("output"),
                percent=data.get("percent"),
                footer=data.get("footer"),
            )
        elif action == "finish":
            target.finish_workspace(
                data.get("result") or data.get("output") or "Done.",
                status=data.get("status") or "Task completed.",
                percent=int(data.get("percent") or 100),
            )
        elif action == "clear":
            target.clear_workspace()

    def _on_discord_status_update(self, message: str):
        if not message:
            return
        if hasattr(self, "_discord_status_lbl"):
            note = message.strip()
            self._refresh_discord_card(note)
            if self._meeting_overlay is not None:
                try:
                    self._meeting_overlay.raise_()
                except Exception:
                    pass
        else:
            if self._meeting_overlay is not None:
                self._meeting_overlay.hide()
            self._meeting_overlay_collapsed = False

    def _request_stop_meeting(self):
        if self.on_attention_action:
            try:
                self.on_attention_action({"kind": "meeting", "app": "Meeting mode"}, "stop")
            except Exception:
                pass

    def _toggle_meeting_overlay(self):
        if self._meeting_overlay is None:
            return
        self._meeting_overlay_collapsed = not self._meeting_overlay_collapsed
        self._meeting_overlay.set_collapsed(self._meeting_overlay_collapsed)
        self._position_meeting_overlay()
        if not self._meeting_overlay.isVisible():
            self._meeting_overlay.show()
        self._meeting_overlay.raise_()

    def _position_meeting_overlay(self):
        if self._meeting_overlay is None:
            return
        screen = QApplication.primaryScreen().availableGeometry()
        margin = 12
        h = self._meeting_overlay.height()
        w = min(980, max(780, screen.width() - margin * 2))
        x = screen.left() + (screen.width() - w) // 2
        y = screen.top() + margin
        self._meeting_overlay.setGeometry(x, y, w, h)

    def _show_attention_alert(self, event: object):
        data = event if isinstance(event, dict) else {}
        if self._incoming_alert is not None:
            try:
                self._incoming_alert.close()
            except Exception:
                pass
            self._incoming_alert = None

        dlg = IncomingAlertDialog(data, self)
        dlg.decision.connect(lambda decision, ev=data: self._attention_choice(ev, decision))

        if (data.get("kind") or "").strip().lower() == "call":
            self.show_app()

        geo = self.frameGeometry()
        if geo.width() <= 0 or geo.height() <= 0:
            screen = QApplication.primaryScreen().availableGeometry()
            cx = screen.center().x()
            cy = screen.center().y()
        else:
            cx = geo.center().x()
            cy = geo.center().y()
        dlg.adjustSize()
        dlg.move(cx - dlg.width() // 2, cy - dlg.height() // 2)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        self._incoming_alert = dlg

    def _attention_choice(self, event: dict, decision: str):
        if self.on_attention_action:
            try:
                self.on_attention_action(event, decision)
            except Exception:
                pass
        self._incoming_alert = None

    def _show_setup(self, defaults: dict | None = None):
        if self._overlay:
            self._overlay.hide()
            self._overlay.deleteLater()
            self._overlay = None
        ov = SetupOverlay(self.centralWidget(), defaults=defaults or self._load_api_defaults())
        cw = self.centralWidget()
        ow, oh = 460, 430
        ov.setGeometry(
            (cw.width()  - ow) // 2,
            (cw.height() - oh) // 2,
            ow, oh,
        )
        ov.done.connect(self._on_setup_done)
        ov.show()
        ov.raise_()
        ov.activateWindow()
        self._overlay = ov

    # Change signature:
    def _on_setup_done(self, key: str, or_key: str, os_name: str):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            API_FILE.write_text(
                json.dumps({
                    "gemini_api_key":    key,
                    "openrouter_api_key": or_key,
                    "os_system":         os_name,
                }, indent=4),
                encoding="utf-8",
            )
            self._ready = True
            self._api_ready = True
            if self._overlay:
                self._overlay.hide()
                self._overlay.deleteLater()
                self._overlay = None
            self._apply_state("LISTENING")
            self._log.append_log(f"SYS: Initialised. OS={os_name.upper()}. Brahma AI online.")
        except Exception as e:
            self._log.append_log(f"ERR: setup failed: {e}")
            traceback.print_exc()

    def _build_left_panel_modern(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(_LEFT_W)
        w.setStyleSheet("QWidget { background: transparent; border-right: none; }")
        root_lay = QVBoxLayout(w)
        root_lay.setContentsMargins(14, 14, 14, 14)
        root_lay.setSpacing(12)

        toggle_row = QHBoxLayout()
        self._left_toggle_btn = QPushButton("<")
        self._left_toggle_btn.setFixedSize(34, 34)
        self._left_toggle_btn.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._left_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._left_toggle_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(12,14,18,245); color: {C.WHITE}; border: 1px solid {C.BORDER_B}; border-radius: 8px; }}"
            f"QPushButton:hover {{ color: {C.PRI}; border: 1px solid {C.PRI}; }}"
        )
        self._left_toggle_btn.clicked.connect(self._toggle_left_sidebar)
        toggle_row.addWidget(self._left_toggle_btn)
        toggle_row.addStretch()
        root_lay.addLayout(toggle_row)

        self._left_content = QWidget()
        self._left_content.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(self._left_content)
        lay.setContentsMargins(2, 8, 2, 4)
        lay.setSpacing(12)
        root_lay.addWidget(self._left_content, stretch=1)

        def section(title: str):
            lbl = QLabel(title.upper())
            lbl.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
            lbl.setStyleSheet(f"color: #8a909a; background: transparent; letter-spacing: 1px;")
            return lbl

        class NavItem(QFrame):
            clicked = pyqtSignal()

            def __init__(self, text: str, active: bool = False, letter: str | None = None, compact: bool = False):
                super().__init__()
                self._compact = compact
                self._letter = (letter or text[:1]).upper()
                self._text = text
                self._active = bool(active)
                self.setObjectName("LeftNavItem")
                self.setFixedHeight(42 if compact else 44)
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                r = QHBoxLayout(self)
                r.setContentsMargins(12, 0, 12, 0)
                r.setSpacing(10)
                self._icon = QLabel(self._letter)
                self._icon.setFixedSize(22, 22)
                self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self._icon.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                self._glow = QWidget(self)
                self._glow.setObjectName("NavGlow")
                self._glow.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                self._glow.setStyleSheet("background: transparent; border: none;")
                self._glow.setGeometry(2, 2, self.width() - 4, self.height() - 4)
                self._glow_effect = QGraphicsOpacityEffect(self._glow)
                self._glow_effect.setOpacity(0.0)
                self._glow.setGraphicsEffect(self._glow_effect)
                self._hover_anim = QPropertyAnimation(self._glow_effect, b"opacity", self)
                self._hover_anim.setDuration(180)
                self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                self._lbl = QLabel(text)
                self._lbl.setFont(QFont("Segoe UI", 10 if compact else 11, QFont.Weight.Bold if active else QFont.Weight.Normal))
                self._arrow = QLabel(">")
                self._arrow.setFont(QFont("Segoe UI", 10))
                self._arrow.setStyleSheet("background: transparent;")
                r.addWidget(self._icon)
                r.addWidget(self._lbl)
                r.addStretch()
                r.addWidget(self._arrow)
                self.set_active(active)

            def set_active(self, active: bool):
                self._active = bool(active)
                self.setStyleSheet(
                    f"""
                    QFrame#LeftNavItem {{
                        background: {"qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(255,69,69,42), stop:0.65 rgba(20,20,24,235), stop:1 rgba(12,12,16,205))" if self._active else "transparent"};
                        border: 1px solid {"%s" % C.PRI if self._active else "transparent"};
                        border-left: 2px solid {"%s" % C.PRI if self._active else "transparent"};
                        border-radius: 2px;
                    }}
                    QFrame#LeftNavItem:hover {{
                        background: rgba(255,69,69,28);
                        border: 1px solid {C.PRI};
                    }}
                    """
                )
                self._icon.setStyleSheet(
                    f"color: {C.PRI if self._active else C.WHITE}; background: rgba(255,255,255,0.03); border: 1px solid {C.PRI if self._active else C.BORDER}; border-radius: 11px;"
                )
                self._glow.setStyleSheet(
                    f"background: rgba(255,69,69,0.10); border: 1px solid rgba(255,69,69,0.20); border-radius: 12px;"
                )
                self._lbl.setFont(QFont("Segoe UI", 10 if self._compact else 11, QFont.Weight.Bold if self._active else QFont.Weight.Normal))
                self._lbl.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
                self._arrow.setVisible(self._active)
                if self._active:
                    self._arrow.setStyleSheet(f"color: {C.PRI}; background: transparent;")

            def resizeEvent(self, event):
                super().resizeEvent(event)
                self._glow.setGeometry(2, 2, self.width() - 4, self.height() - 4)

            def enterEvent(self, event):
                super().enterEvent(event)
                if self._active:
                    return
                self._hover_anim.stop()
                self._hover_anim.setStartValue(self._glow_effect.opacity())
                self._hover_anim.setEndValue(0.24)
                self._hover_anim.start()

            def leaveEvent(self, event):
                super().leaveEvent(event)
                if self._active:
                    return
                self._hover_anim.stop()
                self._hover_anim.setStartValue(self._glow_effect.opacity())
                self._hover_anim.setEndValue(0.0)
                self._hover_anim.start()

            def mousePressEvent(self, event):
                super().mousePressEvent(event)
                if event.button() == Qt.MouseButton.LeftButton:
                    self.clicked.emit()

        self._nav_items: dict[str, NavItem] = {}
        def activate(page: str):
            for name, item in self._nav_items.items():
                item.set_active(name == page)
            self._set_page(page)

        brand = QWidget()
        brand_lay = QHBoxLayout(brand)
        brand_lay.setContentsMargins(0, 0, 0, 0)
        brand_lay.setSpacing(14)
        brand_lay.addWidget(_framed_logo(62, 44, bg="rgba(9,10,14,245)", border=C.BORDER_B, radius=10, inset=8))
        brand_text = QVBoxLayout()
        brand_text.setSpacing(2)
        title = QLabel("<span style='color:#ff4545;'>BRAHMA</span><br><span style='color:#ffffff;'>LITE</span>")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("background: transparent; line-height: 110%;")
        sub = QLabel("Your AI Assistant")
        sub.setFont(QFont("Segoe UI", 9))
        sub.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; padding-top: 2px;")
        brand_text.addWidget(title)
        brand_text.addWidget(sub)
        brand_lay.addLayout(brand_text)
        lay.addWidget(brand)

        lay.addWidget(section("Workspace"))
        self._nav_items["dashboard"] = NavItem("Dashboard", active=True, letter="[]")
        self._nav_items["home"] = NavItem("Brahma Home", active=False, letter="H")
        self._nav_items["settings"] = NavItem("System & Connect", letter="S")
        self._nav_items["dashboard"].clicked.connect(lambda: activate("dashboard"))
        self._nav_items["home"].clicked.connect(lambda: activate("home"))
        self._nav_items["settings"].clicked.connect(lambda: activate("settings"))
        lay.addWidget(self._nav_items["dashboard"])
        lay.addWidget(self._nav_items["home"])
        lay.addWidget(self._nav_items["settings"])

        self._gesture_preview = GestureCameraPreview()
        self._gesture_preview.setFixedHeight(230)
        lay.addWidget(self._gesture_preview)

        lay.addStretch(1)

        status_card = QFrame()
        status_card.setFixedHeight(78)
        status_card.setObjectName("LeftStatusCard")
        status_card.setStyleSheet(f"""
            QFrame#LeftStatusCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(15, 17, 22, 236),
                    stop:1 rgba(8, 10, 14, 218));
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 16px;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        status_lay = QVBoxLayout(status_card)
        status_lay.setContentsMargins(14, 10, 14, 10)
        status_lay.setSpacing(5)
        online = QLabel("<span style='color:#37ff5f;'>●</span> <span style='color:#a9ffb9; font-weight:700;'>System Online</span>")
        online.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        name = QLabel("Brahma AI - Lite")
        name.setFont(QFont("Segoe UI", 9))
        name.setStyleSheet(f"color: {C.TEXT_MED};")
        ver = QLabel("Version 1.0.0 • Gemini 2.5 Flash")
        ver.setFont(QFont("Segoe UI", 8))
        ver.setStyleSheet(f"color: {C.TEXT_DIM};")
        status_lay.addWidget(online)
        status_lay.addWidget(name)
        status_lay.addWidget(ver)
        lay.addWidget(status_card)

        self._apply_sidebar_state()
        return w

    def _build_center_panel_modern(self, face_path: str) -> QWidget:
        w = QWidget()
        w.setObjectName("CenterStage")
        w.setStyleSheet("QWidget#CenterStage { background: transparent; border-left: none; border-right: none; }")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(28, 22, 28, 22)
        lay.setSpacing(14)

        stage_frame = QFrame()
        stage_frame.setObjectName("StageFrame")
        stage_frame.setStyleSheet("QFrame#StageFrame { background: transparent; border: none; }")
        stage = QVBoxLayout(stage_frame)
        stage.setContentsMargins(26, 22, 26, 22)
        stage.setSpacing(14)
        lay.addWidget(stage_frame, stretch=1)

        top_row = QHBoxLayout()
        top_row.setSpacing(14)
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self._core_lbl = QLabel("Good Morning")
        self._core_lbl.setFont(QFont("Segoe UI", 22, QFont.Weight.Black))
        self._core_lbl.setStyleSheet(f"color: {C.WHITE}; background: transparent; letter-spacing: 1px;")
        self._core_sub_lbl = QLabel("Ready to assist.")
        self._core_sub_lbl.setFont(QFont("Segoe UI", 9))
        self._core_sub_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        self._core_status_lbl = QLabel("Brahma is ready. Gemini 2.5 Flash · OpenRouter · Voice Connected · Memory Enabled")
        self._core_status_lbl.setWordWrap(True)
        self._core_status_lbl.setFont(QFont("Segoe UI", 8))
        self._core_status_lbl.setStyleSheet(f"color: #9da8b7; background: transparent;")
        title_box.addWidget(self._core_lbl)
        title_box.addWidget(self._core_sub_lbl)
        title_box.addWidget(self._core_status_lbl)
        top_row.addLayout(title_box)
        top_row.addStretch()

        time_card = QFrame()
        time_card.setObjectName("TimeCard")
        time_card.setStyleSheet("""
            QFrame#TimeCard {
                background: rgba(8, 10, 14, 220);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 16px;
            }
        """)
        time_lay = QVBoxLayout(time_card)
        time_lay.setContentsMargins(12, 10, 12, 10)
        time_lay.setSpacing(2)
        self._clock_lbl = QLabel("00:00")
        self._clock_lbl.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self._clock_lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        self._clock_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._date_lbl = QLabel("")
        self._date_lbl.setFont(QFont("Segoe UI", 8))
        self._date_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        self._date_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._time_status_lbl = QLabel("Online")
        self._time_status_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self._time_status_lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent;")
        self._time_status_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._cpu_lbl = QLabel("CPU 0%")
        self._cpu_lbl.setFont(QFont("Segoe UI", 8))
        self._cpu_lbl.setStyleSheet(f"color: #9da8b7; background: transparent;")
        self._cpu_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._ram_lbl = QLabel("RAM 0%")
        self._ram_lbl.setFont(QFont("Segoe UI", 8))
        self._ram_lbl.setStyleSheet(f"color: #9da8b7; background: transparent;")
        self._ram_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        time_lay.addWidget(self._clock_lbl)
        time_lay.addWidget(self._date_lbl)
        time_lay.addWidget(self._time_status_lbl)
        time_lay.addWidget(self._cpu_lbl)
        time_lay.addWidget(self._ram_lbl)
        top_row.addWidget(time_card)
        stage.addLayout(top_row)

        self._status_chip = QLabel("● Online")
        self._status_chip.setFont(QFont("Segoe UI", 9))
        self._status_chip.setFixedWidth(118)
        self._status_chip.setStyleSheet(
            f"color: {C.GREEN}; background: rgba(11,12,16,238); border: 1px solid rgba(255,255,255,0.10); border-radius: 999px; padding: 7px 14px;"
        )
        stage.addWidget(self._status_chip, alignment=Qt.AlignmentFlag.AlignLeft)

        self._command_card = SmallPanelCard("COMMAND", "hey", accent=C.WHITE)
        self._command_card.setFixedWidth(185)
        self._result_card = SmallPanelCard("ACTION RESULT", "Action completed", accent=C.WHITE)
        self._result_card.setFixedWidth(185)
        self._command_card.hide()
        self._result_card.hide()

        self.hud = HudCanvas(face_path)
        self.hud.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.hud.setMinimumSize(240, 240)
        self.hud.setMaximumSize(280, 280)
        hud_wrap = QFrame()
        hud_wrap.setStyleSheet("background: transparent;")
        hud_lay = QVBoxLayout(hud_wrap)
        hud_lay.setContentsMargins(0, 0, 0, 0)
        hud_lay.setSpacing(0)
        hud_lay.addWidget(self.hud, alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        command_row = QHBoxLayout()
        command_row.setSpacing(14)
        command_row.addWidget(self._command_card, alignment=Qt.AlignmentFlag.AlignVCenter)
        command_row.addWidget(hud_wrap, stretch=1)
        command_row.addWidget(self._result_card, alignment=Qt.AlignmentFlag.AlignVCenter)
        stage.addLayout(command_row, stretch=1)

        # Quick Actions and Suggested Actions removed per user request; keep small spacer
        spacer = QWidget()
        spacer.setFixedHeight(8)
        spacer.setStyleSheet("background: transparent;")
        stage.addWidget(spacer)

        self._command_panel = QWidget()
        self._command_panel.setStyleSheet("background: transparent;")
        cmd_lay = QVBoxLayout(self._command_panel)
        cmd_lay.setContentsMargins(0, 4, 0, 0)
        cmd_lay.setSpacing(10)
        cmd_lay.addLayout(self._build_command_row())
        stage.addWidget(self._command_panel)
        self._home_page = BrahmaHomePage()
        self._center_stack = QStackedWidget()
        self._center_stack.setStyleSheet("background: transparent; border: none;")
        self._center_stack.addWidget(w)
        self._center_stack.addWidget(self._home_page)
        self._settings_page = SystemConnectivityPage()
        self._center_stack.addWidget(self._settings_page)
        self._center_stack.setCurrentIndex(0)
        return self._center_stack

    def _build_right_panel_modern(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(_RIGHT_W)
        w.setStyleSheet("QWidget { background: transparent; border-left: none; }")
        root_lay = QVBoxLayout(w)
        root_lay.setContentsMargins(14, 14, 14, 14)
        root_lay.setSpacing(12)

        toggle_row = QHBoxLayout()
        toggle_row.addStretch()
        self._right_toggle_btn = QPushButton(">")
        self._right_toggle_btn.setFixedSize(34, 34)
        self._right_toggle_btn.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._right_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._right_toggle_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(12,14,18,245); color: {C.WHITE}; border: 1px solid {C.BORDER_B}; border-radius: 8px; }}"
            f"QPushButton:hover {{ color: {C.PRI}; border: 1px solid {C.PRI}; }}"
        )
        self._right_toggle_btn.clicked.connect(self._toggle_right_sidebar)
        toggle_row.addWidget(self._right_toggle_btn)
        root_lay.addLayout(toggle_row)

        self._right_stack = QStackedWidget()
        self._right_stack.setStyleSheet("background: transparent; border: none;")

        self._right_content = QWidget()
        self._right_content.setStyleSheet("background: transparent;")
        chat_lay = QVBoxLayout(self._right_content)
        chat_lay.setContentsMargins(0, 4, 0, 0)
        chat_lay.setSpacing(8)

        self._inline_workspace = InlineChatWorkspace()
        self._inline_workspace.attach_requested.connect(self._browse_attachment)
        self._inline_workspace.mic_requested.connect(self._toggle_mute)
        self._inline_workspace.command_submitted.connect(self._send)
        self._log = self._inline_workspace
        chat_lay.addWidget(self._inline_workspace, stretch=1)

        self._settings_sidebar = SystemConnectivitySidebar()
        self._empty_right = QWidget()
        self._empty_right.setStyleSheet("background: transparent;")

        self._right_stack.addWidget(self._right_content)
        self._right_stack.addWidget(self._settings_sidebar)
        self._right_stack.addWidget(self._empty_right)
        root_lay.addWidget(self._right_stack, stretch=1)

        self._apply_sidebar_state()
        return w

    def _build_command_row(self) -> QHBoxLayout:
        wrapper = QHBoxLayout()
        wrapper.setContentsMargins(0, 0, 0, 0)
        wrapper.setSpacing(0)

        bar = QFrame()
        bar.setFixedHeight(84)
        bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        bar.setStyleSheet(
            f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(10, 11, 14, 248),
                    stop:0.48 rgba(16, 17, 21, 246),
                    stop:1 rgba(10, 11, 14, 248));
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 24px;
            }}
            """
        )
        row = QHBoxLayout(bar)
        row.setContentsMargins(18, 16, 18, 16)
        row.setSpacing(12)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Ask Brahma anything...")
        self._input.setFont(QFont("Segoe UI", 10))
        self._input.setFixedHeight(50)
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(255,255,255,0.03);
                color: {C.WHITE};
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 999px;
                padding: 0 14px;
                selection-background-color: rgba(255,255,255,0.15);
            }}
            QLineEdit:focus {{ border: 1px solid rgba(255,69,69,0.38); }}
        """)
        self._input.returnPressed.connect(self._send)
        row.addWidget(self._input, stretch=1)

        icon_button_style = f"""
            QPushButton {{
                background: rgba(14,15,19,245);
                color: {C.WHITE};
                border: 1px solid {C.BORDER_B};
                border-radius: 7px;
            }}
            QPushButton:hover {{
                background: rgba(255,69,69,24);
                color: {C.PRI};
                border: 1px solid {C.PRI};
            }}
            QPushButton:pressed {{
                background: rgba(255,69,69,48);
            }}
        """

        attach = QPushButton()
        attach.setFixedSize(44, 44)
        attach.setCursor(Qt.CursorShape.PointingHandCursor)
        attach.setToolTip("Attach file")
        attach.setIcon(QIcon(_icon_pixmap("attach", 20)))
        attach.setIconSize(QSize(20, 20))
        attach.setStyleSheet(icon_button_style)
        attach.clicked.connect(self._browse_attachment)
        row.addWidget(attach)

        mic = QPushButton()
        mic.setFixedSize(44, 44)
        mic.setCursor(Qt.CursorShape.PointingHandCursor)
        mic.setToolTip("Microphone")
        mic.setIcon(QIcon(_icon_pixmap("mic", 20)))
        mic.setIconSize(QSize(20, 20))
        mic.setStyleSheet(f"""
            QPushButton {{
                background: rgba(20, 12, 13, 245);
                color: {C.PRI};
                border: 1px solid {C.PRI};
                border-radius: 7px;
            }}
            QPushButton:hover {{
                background: rgba(255,69,69,30);
                border: 1px solid {C.PRI_DIM};
            }}
            QPushButton:pressed {{
                background: rgba(255,69,69,48);
            }}
        """)
        mic.clicked.connect(self._toggle_mute)
        row.addWidget(mic)

        self._send_btn = QPushButton()
        self._send_btn.setFixedSize(44, 44)
        self._send_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.setIcon(QIcon(_icon_pixmap("send", 20)))
        self._send_btn.setIconSize(QSize(20, 20))
        self._send_btn.setStyleSheet(icon_button_style)
        self._send_btn.clicked.connect(self._send)
        row.addWidget(self._send_btn)

        wrapper.addWidget(bar)
        return wrapper

class SystemConnectivitySidebar(QFrame):
    def __init__(self, controller=None, parent=None):
        super().__init__(parent)
        self._controller = controller
        self.setObjectName("SystemConnectivitySidebar")
        self.setStyleSheet(
            f"""
            QFrame#SystemConnectivitySidebar {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(14, 16, 22, 235),
                    stop:1 rgba(7, 9, 13, 220));
                border: 1px solid rgba(255, 255, 255, 0.14);
                border-radius: 22px;
            }}
            QLabel {{
                background: transparent;
            }}
            QPushButton {{
                background: rgba(255,255,255,0.03);
                color: {C.WHITE};
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                text-align: left;
                padding: 10px 12px;
            }}
            QPushButton:hover {{
                background: rgba(255,69,69,0.10);
                border: 1px solid {C.PRI};
            }}
            """
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(14)

        title = QLabel("SYSTEM STATUS")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.WHITE}; letter-spacing: 1px;")
        lay.addWidget(title)

        self._status_card = QFrame()
        self._status_card.setStyleSheet("QFrame { background: rgba(14,16,20,0.88); border: 1px solid rgba(53,255,117,0.18); border-radius: 14px; }")
        s_lay = QVBoxLayout(self._status_card)
        s_lay.setContentsMargins(16, 14, 16, 14)
        s_lay.setSpacing(10)
        self._online_lbl = QLabel("● System Online")
        self._online_lbl.setStyleSheet("color: #35ff75; font-weight: 700;")
        self._desc_lbl = QLabel("All systems are operational.")
        self._desc_lbl.setStyleSheet(f"color: {C.TEXT_MED};")
        s_lay.addWidget(self._online_lbl)
        s_lay.addWidget(self._desc_lbl)
        lay.addWidget(self._status_card)

        self._info_rows: dict[str, QLabel] = {}
        for label in ("Version", "Platform", "Current AI Provider", "Last Updated"):
            row = QHBoxLayout()
            row.setContentsMargins(0, 4, 0, 4)
            row.setSpacing(10)
            icon = QLabel("◌")
            icon.setFixedWidth(18)
            icon.setStyleSheet(f"color: {C.WHITE};")
            key_lbl = QLabel(label)
            key_lbl.setStyleSheet(f"color: {C.WHITE};")
            val_lbl = QLabel("")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            val_lbl.setStyleSheet(f"color: {C.TEXT_MED};")
            row.addWidget(icon)
            row.addWidget(key_lbl)
            row.addStretch(1)
            row.addWidget(val_lbl)
            lay.addLayout(row)
            self._info_rows[label] = val_lbl

        quick_title = QLabel("QUICK ACTIONS")
        quick_title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        quick_title.setStyleSheet(f"color: {C.WHITE}; letter-spacing: 1px;")
        lay.addWidget(quick_title)

        self._quick_actions = QVBoxLayout()
        self._quick_actions.setSpacing(10)
        lay.addLayout(self._quick_actions)
        self._mk_quick_action("↻ Restart Brahma AI", QStyle.StandardPixmap.SP_BrowserReload, self._restart)
        self._mk_quick_action("⟳ Reload Configuration", QStyle.StandardPixmap.SP_BrowserReload, self._reload)
        self._mk_quick_action("📁 Open Data Folder", QStyle.StandardPixmap.SP_DirOpenIcon, self._open_data_folder)
        self._mk_quick_action("📄 View Logs", QStyle.StandardPixmap.SP_FileDialogDetailedView, self._view_logs)
        self._mk_quick_action("⬇ Check for Updates", QStyle.StandardPixmap.SP_ArrowDown, self._check_updates)

        tip = QFrame()
        tip.setStyleSheet("QFrame { background: rgba(24, 18, 8, 0.85); border: 1px solid rgba(255, 191, 0, 0.22); border-radius: 14px; }")
        tip_lay = QVBoxLayout(tip)
        tip_lay.setContentsMargins(16, 14, 16, 14)
        tip_lay.setSpacing(8)
        tip_title = QLabel("Security Tip")
        tip_title.setStyleSheet("color: #ffbf00; font-weight: 700;")
        tip_body = QLabel('"Never share your API keys with anyone."')
        tip_body.setWordWrap(True)
        tip_body.setStyleSheet(f"color: {C.TEXT_MED};")
        tip_lay.addWidget(tip_title)
        tip_lay.addWidget(tip_body)
        lay.addStretch(1)
        lay.addWidget(tip)

        self.refresh()

    def set_controller(self, controller):
        self._controller = controller
        self.refresh()

    def _mk_quick_action(self, text: str, icon_kind, slot):
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setIcon(self.style().standardIcon(icon_kind))
        btn.clicked.connect(slot)
        self._quick_actions.addWidget(btn)
        return btn

    def _bridge(self):
        return self._controller

    def _restart(self):
        if self._bridge() and hasattr(self._bridge(), "_restart_app"):
            self._bridge()._restart_app()

    def _reload(self):
        if self._bridge() and hasattr(self._bridge(), "_win"):
            try:
                self._bridge()._win._load_api_defaults()
                self._bridge()._win._load_discord_settings()
                self._bridge()._log_sig.emit("SYS: Configuration reloaded.")
            except Exception:
                pass

    def _open_data_folder(self):
        try:
            os.startfile(str(CONFIG_DIR))
        except Exception:
            pass

    def _view_logs(self):
        try:
            os.startfile(str(BASE_DIR))
        except Exception:
            pass

    def _check_updates(self):
        if self._bridge() and hasattr(self._bridge(), "write_log"):
            self._bridge().write_log("SYS: Update check is not connected to a remote service yet.")

    def refresh(self):
        if self._bridge() and hasattr(self._bridge(), "_win"):
            version = "v1.0.0"
            platform_name = platform.system()
            provider = self._bridge()._win._load_app_settings().get("default_ai_provider", "Gemini")
            last_updated = time.strftime("%d %b %Y %H:%M")
            self._info_rows["Version"].setText(version)
            self._info_rows["Platform"].setText(platform_name)
            self._info_rows["Current AI Provider"].setText(provider)
            self._info_rows["Last Updated"].setText(last_updated)
        else:
            self._info_rows["Version"].setText("v1.0.0")
            self._info_rows["Platform"].setText(platform.system())
            self._info_rows["Current AI Provider"].setText("Gemini")
            self._info_rows["Last Updated"].setText(time.strftime("%d %b %Y %H:%M"))


class SystemConnectivityPage(QWidget):
    def __init__(self, controller=None, parent=None):
        super().__init__(parent)
        self._controller = controller
        self.setObjectName("SystemConnectivityPage")
        self.setStyleSheet(f"""
            QWidget#SystemConnectivityPage {{
                background: transparent;
            }}
            QFrame#SettingsCard {{
                background: rgba(10,11,15,235);
                border: 1px solid rgba(255,69,69,0.18);
                border-radius: 18px;
            }}
            QLabel {{
                background: transparent;
            }}
            QPushButton {{
                background: rgba(255,255,255,0.03);
                color: {C.WHITE};
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                padding: 10px 12px;
            }}
            QPushButton:hover {{
                background: rgba(255,69,69,0.10);
                border: 1px solid {C.PRI};
            }}
            QLineEdit, QComboBox {{
                background: rgba(13,15,19,240);
                color: {C.WHITE};
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                min-height: 34px;
                padding: 0 10px;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border: 1px solid {C.PRI};
            }}
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        root.addWidget(self._scroll)

        self._content = QWidget()
        self._scroll.setWidget(self._content)
        lay = QVBoxLayout(self._content)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)

        header = QFrame()
        header.setStyleSheet("background: transparent; border: none;")
        h_lay = QVBoxLayout(header)
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(6)
        title = QLabel("SYSTEM & CONNECTIVITY")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.Black))
        title.setStyleSheet(f"color: {C.WHITE}; letter-spacing: 1px;")
        sub = QLabel("Manage your AI providers, connections and application preferences.")
        sub.setFont(QFont("Segoe UI", 10))
        sub.setStyleSheet(f"color: {C.TEXT_DIM};")
        h_lay.addWidget(title)
        h_lay.addWidget(sub)
        lay.addWidget(header)

        top = QHBoxLayout()
        top.setSpacing(14)
        top.addWidget(self._build_left_column(), 7)
        top.addWidget(self._build_summary_card(), 3)
        lay.addLayout(top)
        lay.addStretch(1)

        self.refresh()

    def set_controller(self, controller):
        self._controller = controller
        self.refresh()

    def _ctrl(self):
        return self._controller

    def _card(self, title: str, subtitle: str = "") -> QFrame:
        frame = QFrame()
        frame.setObjectName("SettingsCard")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(12)
        head = QLabel(title)
        head.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        head.setStyleSheet(f"color: {C.WHITE};")
        lay.addWidget(head)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setWordWrap(True)
            sub.setStyleSheet(f"color: {C.TEXT_DIM};")
            lay.addWidget(sub)
        return frame

    def _mk_toggle(self, text: str, checked: bool, callback):
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: callback(btn.isChecked()))
        btn.setStyleSheet(
            f"""
            QPushButton {{
                text-align: left;
                background: rgba(255,255,255,0.03);
                color: {C.WHITE};
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                padding: 12px 14px;
            }}
            QPushButton:checked {{
                background: rgba(255,69,69,0.12);
                border: 1px solid {C.PRI};
            }}
            QPushButton:hover {{
                background: rgba(255,69,69,0.08);
            }}
            """
        )
        return btn

    def _provider_key_preview(self, key: str) -> str:
        key = (key or "").strip()
        if not key:
            return "Not set"
        if len(key) <= 8:
            return "••••••••"
        return f"{key[:4]}••••••••{key[-4:]}"

    def _provider_row(self, name: str, key: str, model: str, setting_key: str):
        row = QFrame()
        row.setStyleSheet("QFrame { background: rgba(255,255,255,0.025); border: 1px solid rgba(255,255,255,0.06); border-radius: 14px; }")
        r = QHBoxLayout(row)
        r.setContentsMargins(14, 12, 14, 12)
        r.setSpacing(12)
        icon = QLabel(name[:1].upper())
        icon.setFixedSize(42, 42)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        icon.setStyleSheet(f"background: rgba(255,69,69,0.12); color: {C.WHITE}; border: 1px solid rgba(255,69,69,0.38); border-radius: 21px;")
        r.addWidget(icon)
        meta = QVBoxLayout()
        title = QLabel(name)
        title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.WHITE};")
        status = QLabel("Connected" if key else "Not connected")
        status.setStyleSheet(f"color: {C.GREEN if key else C.PRI};")
        model_lbl = QLabel(f"Current model: {model}")
        model_lbl.setStyleSheet(f"color: {C.TEXT_DIM};")
        api_lbl = QLabel(self._provider_key_preview(key))
        api_lbl.setStyleSheet(f"color: {C.TEXT_MED};")
        meta.addWidget(title)
        meta.addWidget(status)
        meta.addWidget(model_lbl)
        meta.addWidget(api_lbl)
        r.addLayout(meta, 1)
        btn_lay = QVBoxLayout()
        btn_lay.setSpacing(8)
        edit = QPushButton("Edit API Key")
        edit.clicked.connect(lambda: self._open_api_keys())
        test = QPushButton("Test Connection")
        test.clicked.connect(lambda: self._test_provider(setting_key))
        btn_lay.addWidget(edit)
        btn_lay.addWidget(test)
        r.addLayout(btn_lay)
        return row, status, api_lbl

    def _build_left_column(self):
        col = QWidget()
        lay = QVBoxLayout(col)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        # AI Providers
        card = self._card("AI Providers", "Only the supported providers are shown here.")
        lay1 = card.layout()
        self._api_defaults = self._load_api_defaults()
        self._gemini_row, self._gemini_status, self._gemini_key = self._provider_row(
            "Google Gemini",
            self._api_defaults.get("gemini_api_key", ""),
            "gemini-2.5-flash",
            "gemini",
        )
        self._or_row, self._or_status, self._or_key = self._provider_row(
            "OpenRouter",
            self._api_defaults.get("openrouter_api_key", ""),
            "auto",
            "openrouter",
        )
        lay1.addWidget(self._gemini_row)
        lay1.addWidget(self._or_row)
        controls = QHBoxLayout()
        controls.setSpacing(12)
        self._default_provider = QComboBox()
        self._default_provider.addItems(["Google Gemini", "OpenRouter"])
        self._default_provider.setCurrentText("Google Gemini" if self._load_app_settings().get("default_ai_provider", "Gemini") in {"Gemini", "Google Gemini"} else "OpenRouter")
        self._default_provider.currentTextChanged.connect(self._set_default_provider)
        controls.addWidget(QLabel("Default AI Provider"))
        controls.addWidget(self._default_provider, 1)
        lay1.addLayout(controls)
        self._auto_switch_btn = self._mk_toggle("Automatically switch if a provider fails", bool(self._load_app_settings().get("auto_provider_switch", True)), self._toggle_auto_provider_switch)
        lay1.addWidget(self._auto_switch_btn)
        lay.addWidget(card)

        # Mobile connect
        mobile = self._card("Mobile Connect", "Connect your phone and control Brahma remotely.")
        ml = mobile.layout()
        self._mobile_status = QLabel("Connection Status: Ready")
        self._mobile_phone = QLabel("Phone Name: Not connected")
        self._mobile_last = QLabel("Last Connected: Never")
        for lbl in (self._mobile_status, self._mobile_phone, self._mobile_last):
            lbl.setStyleSheet(f"color: {C.TEXT_MED};")
            ml.addWidget(lbl)
        row = QHBoxLayout()
        self._mobile_connect_btn = QPushButton("Connect Device")
        self._mobile_connect_btn.clicked.connect(self._connect_mobile)
        self._mobile_disconnect_btn = QPushButton("Disconnect")
        self._mobile_disconnect_btn.clicked.connect(self._disconnect_mobile)
        self._mobile_qr_btn = QPushButton("Generate QR Code")
        self._mobile_qr_btn.clicked.connect(self._show_qr_code)
        row.addWidget(self._mobile_connect_btn)
        row.addWidget(self._mobile_disconnect_btn)
        row.addWidget(self._mobile_qr_btn)
        ml.addLayout(row)
        lay.addWidget(mobile)

        # Attention prompts
        attention = self._card("Attention Prompts", "Control incoming message and call alerts.")
        al = attention.layout()
        self._attention_message_btn = self._mk_toggle(
            "Show incoming message prompts",
            bool(self._load_app_settings().get("attention_message_prompts", True)),
            self._toggle_attention_message_prompts,
        )
        self._attention_call_btn = self._mk_toggle(
            "Show incoming call prompts",
            bool(self._load_app_settings().get("attention_call_prompts", True)),
            self._toggle_attention_call_prompts,
        )
        al.addWidget(self._attention_message_btn)
        al.addWidget(self._attention_call_btn)
        lay.addWidget(attention)

        # Startup
        startup = self._card("Startup", "Use Brahma with Windows startup preferences.")
        sl = startup.layout()
        self._startup_launch_btn = self._mk_toggle("Launch Brahma AI when Windows starts", bool(self._load_app_settings().get("show_workspace_on_startup", False)), self._toggle_startup_from_page)
        self._startup_minimized_btn = self._mk_toggle("Launch Minimized", bool(self._load_app_settings().get("launch_minimized", False)), self._toggle_launch_minimized)
        self._startup_updates_btn = self._mk_toggle("Check for updates on startup", bool(self._load_app_settings().get("check_updates_on_startup", True)), self._toggle_update_check)
        sl.addWidget(self._startup_launch_btn)
        sl.addWidget(self._startup_minimized_btn)
        sl.addWidget(self._startup_updates_btn)
        lay.addWidget(startup)

        # Startup animation
        anim = self._card("Startup Animation", "Control how the boot sequence behaves.")
        al = anim.layout()
        self._startup_anim_enable_btn = self._mk_toggle("Enable Startup Animation", bool(self._startup_animation_enabled()), self._toggle_startup_animation_from_page)
        al.addWidget(self._startup_anim_enable_btn)
        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Animation Speed"))
        self._anim_speed = QComboBox()
        self._anim_speed.addItems(["Fast", "Normal", "Slow"])
        self._anim_speed.setCurrentText(self._load_app_settings().get("startup_anim_speed", "Normal"))
        speed_row.addWidget(self._anim_speed, 1)
        al.addLayout(speed_row)
        self._anim_preview_btn = QPushButton("Preview Animation")
        self._anim_preview_btn.clicked.connect(self._preview_animation)
        al.addWidget(self._anim_preview_btn)
        self._preview_progress = QProgressBar()
        self._preview_progress.setRange(0, 100)
        self._preview_progress.setValue(0)
        self._preview_progress.setTextVisible(False)
        self._preview_progress.setFixedHeight(8)
        self._preview_progress.setStyleSheet("QProgressBar { background: rgba(255,255,255,0.05); border: none; border-radius: 4px; } QProgressBar::chunk { background: #ff4545; border-radius: 4px; }")
        al.addWidget(self._preview_progress)
        lay.addWidget(anim)

        # Discord bot
        discord = self._card("Discord Bot", "Mirror Brahma between the app and your server.")
        dl = discord.layout()
        self._discord_defaults = self._load_discord_settings()
        self._discord_status = QLabel("Bot Status: Offline")
        dl.addWidget(self._discord_status)
        self._discord_token = QLineEdit()
        self._discord_token.setEchoMode(QLineEdit.EchoMode.Password)
        self._discord_token.setPlaceholderText("Bot Token")
        self._discord_token.setText((self._discord_defaults.get("bot_token") or "").strip())
        self._discord_token.setCursorPosition(0)
        dl.addWidget(self._discord_token)
        self._discord_reveal = QPushButton("Reveal")
        self._discord_reveal.setCheckable(True)
        self._discord_reveal.clicked.connect(self._toggle_discord_reveal)
        dl.addWidget(self._discord_reveal)
        self._discord_channel = QLineEdit()
        self._discord_channel.setPlaceholderText("Optional Channel ID")
        self._discord_channel.setText((self._discord_defaults.get("channel_id") or "").strip())
        dl.addWidget(self._discord_channel)
        db = QHBoxLayout()
        self._discord_save = QPushButton("Save")
        self._discord_test = QPushButton("Test Connection")
        self._discord_restart = QPushButton("Restart Bot")
        self._discord_save.clicked.connect(self._save_discord_from_page)
        self._discord_test.clicked.connect(self._test_discord_from_page)
        self._discord_restart.clicked.connect(self._restart_discord_from_page)
        db.addWidget(self._discord_save)
        db.addWidget(self._discord_test)
        db.addWidget(self._discord_restart)
        dl.addLayout(db)
        self._discord_msg = QLabel("")
        self._discord_msg.setStyleSheet(f"color: {C.TEXT_DIM};")
        dl.addWidget(self._discord_msg)
        lay.addWidget(discord)

        about = self._card("About Brahma", "Brahma AI Lite information only.")
        ab = about.layout()
        about_grid = QGridLayout()
        about_grid.setHorizontalSpacing(22)
        about_grid.setVerticalSpacing(8)
        entries = [
            ("Version", "v1.0.0"),
            ("Build Number", "2026.06.29"),
            ("Release Date", "29 Jun 2026"),
        ]
        self._about_values: dict[str, QLabel] = {}
        for idx, (label, value) in enumerate(entries):
            key = QLabel(label)
            key.setStyleSheet(f"color: {C.TEXT_DIM};")
            val = QLabel(value)
            val.setStyleSheet(f"color: {C.WHITE}; font-weight: 700;")
            about_grid.addWidget(key, idx, 0)
            about_grid.addWidget(val, idx, 1)
            self._about_values[label] = val
        ab.addLayout(about_grid)
        lay.addWidget(about)

        lay.addStretch(1)
        return col

    def _build_summary_card(self):
        card = self._card("")
        card.layout().setContentsMargins(18, 18, 18, 18)
        card.layout().setSpacing(14)
        card.layout().addWidget(self._build_status_box())
        card.layout().addWidget(self._build_quick_actions_box())
        card.layout().addWidget(self._build_security_tip())
        return card

    def _build_status_box(self):
        box = self._card("System Status", "")
        lay = box.layout()
        self._sys_online = QLabel("🟢 System Online")
        self._sys_online.setStyleSheet("color: #35ff75; font-weight: 700;")
        self._sys_note = QLabel("All systems are operational.")
        self._sys_note.setStyleSheet(f"color: {C.TEXT_MED};")
        lay.addWidget(self._sys_online)
        lay.addWidget(self._sys_note)
        self._sys_version = QLabel("v1.0.0")
        self._sys_platform = QLabel(platform.system())
        self._sys_provider = QLabel("Gemini")
        self._sys_updated = QLabel(time.strftime("%d %b %Y %H:%M"))
        for label, val in (("Version", self._sys_version), ("Platform", self._sys_platform), ("Current AI Provider", self._sys_provider), ("Last Updated", self._sys_updated)):
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            row.addStretch(1)
            row.addWidget(val)
            lay.addLayout(row)
        return box

    def _build_quick_actions_box(self):
        box = self._card("Quick Actions", "")
        lay = box.layout()
        actions = [
            ("Restart Brahma AI", QStyle.StandardPixmap.SP_BrowserReload, self._restart_app),
            ("Reload Configuration", QStyle.StandardPixmap.SP_BrowserReload, self._reload_config),
            ("Open Data Folder", QStyle.StandardPixmap.SP_DirOpenIcon, self._open_data_folder),
            ("View Logs", QStyle.StandardPixmap.SP_FileDialogDetailedView, self._view_logs),
            ("Check for Updates", QStyle.StandardPixmap.SP_ArrowDown, self._check_updates),
        ]
        for text, icon_kind, slot in actions:
            btn = QPushButton(text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setIcon(self.style().standardIcon(icon_kind))
            btn.clicked.connect(slot)
            lay.addWidget(btn)
        return box

    def _build_security_tip(self):
        box = QFrame()
        box.setStyleSheet("QFrame { background: rgba(24, 18, 8, 0.85); border: 1px solid rgba(255, 191, 0, 0.22); border-radius: 14px; }")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)
        title = QLabel("Security Tip")
        title.setStyleSheet("color: #ffbf00; font-weight: 700;")
        body = QLabel('"Never share your API keys with anyone."')
        body.setWordWrap(True)
        body.setStyleSheet(f"color: {C.TEXT_MED};")
        lay.addWidget(title)
        lay.addWidget(body)
        return box

    def _load_api_defaults(self):
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            return self._ctrl()._win._load_api_defaults()
        return {
            "gemini_api_key": "",
            "openrouter_api_key": "",
            "os_system": platform.system(),
        }

    def _load_app_settings(self):
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            return self._ctrl()._win._load_app_settings()
        return _default_app_settings()

    def _load_discord_settings(self):
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            return self._ctrl()._win._load_discord_settings()
        return _default_discord_settings()

    def _startup_animation_enabled(self):
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            return self._ctrl()._win._startup_animation_enabled()
        return True

    def _set_setting(self, key: str, value):
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            settings = self._ctrl()._win._load_app_settings()
            settings[key] = value
            self._ctrl()._win._save_app_settings(settings)

    def _open_api_keys(self):
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            self._ctrl()._win._show_setup(self._ctrl()._win._load_api_defaults())

    def _test_provider(self, setting_key: str):
        if setting_key == "gemini":
            msg = "Google Gemini key detected." if self._load_api_defaults().get("gemini_api_key") else "Google Gemini key missing."
        else:
            msg = "OpenRouter key detected." if self._load_api_defaults().get("openrouter_api_key") else "OpenRouter key missing."
        if self._ctrl() and hasattr(self._ctrl(), "write_log"):
            self._ctrl().write_log(f"SYS: {msg}")
        self.refresh()

    def _connect_mobile(self):
        ctrl = self._ctrl()
        if not ctrl:
            return
        target = None
        if hasattr(ctrl, "_show_remote_connect"):
            target = ctrl
        elif hasattr(ctrl, "_win") and hasattr(ctrl._win, "_show_remote_connect"):
            target = ctrl._win
        if target is not None:
            self._mobile_connect_btn.setText("Connecting...")
            target._show_remote_connect()
            QTimer.singleShot(1100, lambda: self._mobile_connect_btn.setText("Connect Device"))

    def _disconnect_mobile(self):
        if self._ctrl() and hasattr(self._ctrl(), "write_log"):
            self._ctrl().write_log("SYS: Mobile Connect session closed.")
        self._mobile_status.setText("Connection Status: Disconnected")
        self._mobile_phone.setText("Phone Name: Not connected")
        self._mobile_last.setText("Last Connected: Never")

    def _show_qr_code(self):
        ctrl = self._ctrl()
        if not ctrl:
            return
        target = None
        if hasattr(ctrl, "_show_remote_connect"):
            target = ctrl
        elif hasattr(ctrl, "_win") and hasattr(ctrl._win, "_show_remote_connect"):
            target = ctrl._win
        if target is not None:
            target._show_remote_connect()

    def _toggle_startup_from_page(self, checked: bool):
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            self._ctrl()._win._set_startup_enabled(bool(checked))
            self._ctrl()._win._refresh_startup_button()

    def _toggle_launch_minimized(self, checked: bool):
        self._set_setting("launch_minimized", bool(checked))

    def _toggle_update_check(self, checked: bool):
        self._set_setting("check_updates_on_startup", bool(checked))

    def _toggle_startup_animation_from_page(self, checked: bool):
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            self._ctrl()._win._set_startup_animation_enabled(bool(checked))
            self._ctrl()._win._refresh_startup_animation_button()

    def _set_default_provider(self, text: str):
        provider = "Gemini" if (text or "").strip().lower().startswith("google") else "OpenRouter"
        self._set_setting("default_ai_provider", provider)
        if self._ctrl() and hasattr(self._ctrl(), "write_log"):
            self._ctrl().write_log(f"SYS: Default AI provider set to {provider}.")

    def _toggle_auto_provider_switch(self, checked: bool):
        self._set_setting("auto_provider_switch", bool(checked))
        if self._ctrl() and hasattr(self._ctrl(), "write_log"):
            self._ctrl().write_log(f"SYS: Auto provider switch {'enabled' if checked else 'disabled'}.")

    def _toggle_attention_message_prompts(self, checked: bool):
        self._set_setting("attention_message_prompts", bool(checked))
        if self._ctrl() and hasattr(self._ctrl(), "write_log"):
            self._ctrl().write_log(f"SYS: Incoming message prompts {'enabled' if checked else 'disabled'}.")

    def _toggle_attention_call_prompts(self, checked: bool):
        self._set_setting("attention_call_prompts", bool(checked))
        if self._ctrl() and hasattr(self._ctrl(), "write_log"):
            self._ctrl().write_log(f"SYS: Incoming call prompts {'enabled' if checked else 'disabled'}.")

    def _preview_animation(self):
        self._preview_progress.setValue(0)
        if hasattr(self, "_preview_timer") and self._preview_timer:
            try:
                self._preview_timer.stop()
            except Exception:
                pass
        self._preview_timer = QTimer(self)
        self._preview_timer.timeout.connect(self._tick_preview)
        self._preview_timer.start(24)

    def _tick_preview(self):
        value = min(100, self._preview_progress.value() + 4)
        self._preview_progress.setValue(value)
        if value >= 100 and hasattr(self, "_preview_timer"):
            self._preview_timer.stop()
            if self._ctrl() and hasattr(self._ctrl(), "write_log"):
                self._ctrl().write_log("SYS: Startup animation preview finished.")

    def _toggle_discord_reveal(self, checked: bool):
        self._discord_token.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)

    def _save_discord_from_page(self):
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            self._ctrl()._win._discord_token_input = self._discord_token
            self._ctrl()._win._discord_channel_input = self._discord_channel
            self._ctrl()._win._save_discord_token()
            self._discord_status.setText("Bot Status: Saved")
            self.refresh()

    def _test_discord_from_page(self):
        self._save_discord_from_page()
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            self._ctrl()._win._start_discord_bot()
            self._ctrl()._win._stop_discord_bot()
            self._discord_status.setText("Bot Status: Test sent")
            self._discord_msg.setText("Connected as Brahma#9649" if self._discord_token.text().strip() else "Bot Offline")

    def _restart_discord_from_page(self):
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            self._ctrl()._win._stop_discord_bot()
            self._ctrl()._win._start_discord_bot()
            self._discord_status.setText("Bot Status: Restarted")

    def _restart_app(self):
        if self._ctrl() and hasattr(self._ctrl(), "_restart_app"):
            self._ctrl()._restart_app()

    def _reload_config(self):
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            self._ctrl()._win._load_api_defaults()
            self._ctrl()._win._load_discord_settings()
            if hasattr(self._ctrl(), "write_log"):
                self._ctrl().write_log("SYS: Configuration reloaded.")
            self.refresh()

    def _open_data_folder(self):
        try:
            os.startfile(str(CONFIG_DIR))
        except Exception:
            pass

    def _view_logs(self):
        try:
            os.startfile(str(BASE_DIR))
        except Exception:
            pass

    def _check_updates(self):
        if self._ctrl() and hasattr(self._ctrl(), "write_log"):
            self._ctrl().write_log("SYS: Update check requested.")

    def refresh(self):
        api = self._load_api_defaults()
        app = self._load_app_settings()
        discord = self._load_discord_settings()
        for widget in (
            getattr(self, "_default_provider", None),
            getattr(self, "_auto_switch_btn", None),
            getattr(self, "_attention_message_btn", None),
            getattr(self, "_attention_call_btn", None),
            getattr(self, "_startup_launch_btn", None),
            getattr(self, "_startup_minimized_btn", None),
            getattr(self, "_startup_updates_btn", None),
            getattr(self, "_startup_anim_enable_btn", None),
            getattr(self, "_discord_token", None),
            getattr(self, "_discord_channel", None),
            getattr(self, "_discord_reveal", None),
        ):
            if widget is not None:
                widget.blockSignals(True)
        try:
            self._gemini_status.setText("Connected" if api.get("gemini_api_key") else "Not connected")
            self._or_status.setText("Connected" if api.get("openrouter_api_key") else "Not connected")
            self._gemini_key.setText(self._provider_key_preview(api.get("gemini_api_key", "")))
            self._or_key.setText(self._provider_key_preview(api.get("openrouter_api_key", "")))
            self._default_provider.setCurrentText("Google Gemini" if app.get("default_ai_provider", "Gemini") == "Gemini" else "OpenRouter")
            self._auto_switch_btn.setChecked(bool(app.get("auto_provider_switch", True)))
            self._attention_message_btn.setChecked(bool(app.get("attention_message_prompts", True)))
            self._attention_call_btn.setChecked(bool(app.get("attention_call_prompts", True)))
            self._startup_launch_btn.setChecked(bool(app.get("show_workspace_on_startup", False)))
            self._startup_minimized_btn.setChecked(bool(app.get("launch_minimized", False)))
            self._startup_updates_btn.setChecked(bool(app.get("check_updates_on_startup", True)))
            self._startup_anim_enable_btn.setChecked(bool(self._startup_animation_enabled()))
            self._discord_token.setText((discord.get("bot_token") or "").strip())
            self._discord_channel.setText((discord.get("channel_id") or "").strip())
        finally:
            for widget in (
                getattr(self, "_default_provider", None),
                getattr(self, "_auto_switch_btn", None),
                getattr(self, "_attention_message_btn", None),
                getattr(self, "_attention_call_btn", None),
                getattr(self, "_startup_launch_btn", None),
                getattr(self, "_startup_minimized_btn", None),
                getattr(self, "_startup_updates_btn", None),
                getattr(self, "_startup_anim_enable_btn", None),
                getattr(self, "_discord_token", None),
                getattr(self, "_discord_channel", None),
                getattr(self, "_discord_reveal", None),
            ):
                if widget is not None:
                    widget.blockSignals(False)
        enabled = bool(discord.get("enabled", False))
        token = (discord.get("bot_token") or "").strip()
        if enabled and token:
            self._discord_status.setText("Bot Status: Online")
            self._discord_msg.setText("Connected as Brahma#9649")
        elif token:
            self._discord_status.setText("Bot Status: Offline")
            self._discord_msg.setText("Bot Offline")
        else:
            self._discord_status.setText("Bot Status: Offline")
            self._discord_msg.setText("Token required")
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            self._sys_provider.setText("Gemini" if app.get("default_ai_provider", "Gemini") == "Gemini" else "OpenRouter")

class _RootShim:
    def __init__(self, app: QApplication):
        self._app = app
    def mainloop(self):
        self._app.exec()
    def protocol(self, *_):
        pass


class BrahmaUI:
    def __init__(self, face_path: str, size=None, *, show_immediately: bool = True):
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyle("Fusion")
        self._app.setQuitOnLastWindowClosed(False)
        self._app.setApplicationDisplayName("Brahma AI - Lite")
        self._app.setWindowIcon(self._make_app_icon())
        try:
            current_store = workspace_store()
            current_store.rollover_active_conversation_on_startup()
        except Exception:
            pass
        self._win = MainWindow(face_path)
        self._win.set_settings_bridge(self)
        self._discord_service = DiscordBotService(
            status_callback=self._win.discord_status_changed.emit,
            log_callback=self._win._log_sig.emit,
        )
        self._discord_service.bind_app_submitter(self._win.submit_command)
        self._win.discord_config_changed.connect(self._on_discord_config_changed)
        self._win.on_chat_event = self._on_chat_event
        self._app.aboutToQuit.connect(self._discord_service.stop)
        self._launcher = FloatingLauncher()
        self._command_bar = CommandBar()
        self._workspace_sidebar = WorkspaceSidebar()
        self._control_panel: LauncherControlPanel | None = None
        self._boot_overlay: BootSequenceOverlay | None = None
        self._app_settings_cache: dict | None = None
        self._launcher.single_clicked.connect(self._toggle_command_bar)
        self._launcher.double_clicked.connect(self._show_control_panel)
        self._launcher.action_requested.connect(self._handle_launcher_action)
        self._launcher.position_changed.connect(self._save_launcher_position)
        self._command_bar.submitted.connect(self._submit_command)
        self._command_bar.attach_clicked.connect(self._browse_attachment)
        self._command_bar.mic_clicked.connect(self._toggle_mute)
        self._workspace_sidebar.command_submitted.connect(self._submit_command)
        self._workspace_sidebar.attach_requested.connect(self._browse_attachment)
        self._workspace_sidebar.mic_requested.connect(self._toggle_mute)
        self._workspace_sidebar.close_requested.connect(self._close_workspace_sidebar)
        self._win._inline_workspace.attach_requested.connect(self._browse_attachment)
        self._win._inline_workspace.mic_requested.connect(self._toggle_mute)
        self._win._inline_workspace.command_submitted.connect(self._submit_command)
        self._win.minimized.connect(self._on_minimized)
        self._win._state_sig.connect(self._sync_launcher_state)
        self._tray = QSystemTrayIcon(self._make_app_icon(), self._app)
        self._tray.setToolTip("Brahma AI - Lite")
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.setContextMenu(self._build_tray_menu())
        self._tray.show()
        self._win._log_sig.connect(self._workspace_sidebar.append_log)
        self._win._log_sig.connect(self._win._inline_workspace.append_log)
        self._win._task_workspace_sig.connect(self._workspace_sidebar.apply_task_workspace)
        self._win._task_workspace_sig.connect(self._win._inline_workspace.apply_task_workspace)
        self._on_discord_config_changed(self._win._load_discord_settings())
        launcher_pos = self._load_app_settings().get("launcher_pos")
        if isinstance(launcher_pos, (list, tuple)) and len(launcher_pos) == 2:
            try:
                self._launcher.show_at(int(launcher_pos[0]), int(launcher_pos[1]))
            except Exception:
                self._launcher.show_at()
        else:
            self._launcher.show_at()
        if bool(self._load_app_settings().get("show_workspace_on_startup", False)):
            self._workspace_sidebar.show_workspace(animate=False)
        else:
            self._workspace_sidebar.hide_workspace(animate=False)
        self.set_dashboard_page(getattr(self._win, "_current_page", "dashboard") == "dashboard")
        if show_immediately:
            self.show_main()
        self.root = _RootShim(self._app)

    def _make_app_icon(self) -> QIcon:
        return _logo_icon()

    def show_main(self):
        try:
            self._win.showNormal()
        except Exception:
            self._win.show()
        self._win.raise_()
        self._win.activateWindow()
        if self._launcher.isVisible():
            try:
                self._launcher.raise_()
                self._launcher.activateWindow()
            except Exception:
                pass

    def set_dashboard_page(self, enabled: bool):
        try:
            if enabled:
                if not self._launcher.isVisible():
                    self._show_floating_icon()
            else:
                self._command_bar.hide()
                self._workspace_sidebar.hide_workspace(animate=False)
                self._launcher.hide()
        except Exception:
            pass

    def hide_main(self):
        self._command_bar.hide()
        self._launcher.hide()
        self._win.hide()

    def _load_app_settings(self) -> dict:
        if self._app_settings_cache is not None:
            return dict(self._app_settings_cache)
        settings = _default_app_settings()
        if APP_SETTINGS_FILE.exists():
            try:
                data = json.loads(APP_SETTINGS_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    settings.update({k: data.get(k, v) for k, v in settings.items()})
            except Exception:
                pass
        self._app_settings_cache = dict(settings)
        return dict(settings)

    def _save_app_settings(self, settings: dict):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        APP_SETTINGS_FILE.write_text(json.dumps(settings, indent=4), encoding="utf-8")
        self._app_settings_cache = dict(settings)

    def _save_launcher_position(self, x: int, y: int):
        try:
            settings = self._load_app_settings()
            settings["launcher_pos"] = [int(x), int(y)]
            self._save_app_settings(settings)
        except Exception:
            pass

    def _sync_launcher_state(self, state: str):
        state = (state or "idle").strip().lower()
        detail = {
            "listening": "Ready",
            "thinking": "Thinking...",
            "processing": "Executing task...",
            "speaking": "Speaking",
            "muted": "Muted",
        }.get(state, "Ready")
        try:
            self._launcher.set_state(state, detail)
        except Exception:
            pass

    def _load_discord_settings(self) -> dict:
        settings = _default_discord_settings()
        if DISCORD_SETTINGS_FILE.exists():
            try:
                data = json.loads(DISCORD_SETTINGS_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    settings.update({k: data.get(k, v) for k, v in settings.items()})
            except Exception:
                pass
        if (settings.get("bot_token") or "").strip():
            settings["enabled"] = True
        return dict(settings)

    def _save_discord_settings(self, settings: dict):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        DISCORD_SETTINGS_FILE.write_text(json.dumps(settings, indent=4), encoding="utf-8")

    def _emit_discord_settings(self):
        if not hasattr(self, "_discord_token_input"):
            return
        settings = {
            "bot_token": self._discord_token_input.text().strip(),
            "enabled": bool(getattr(self, "_discord_enabled", False)),
            "channel_id": self._discord_channel_input.text().strip() if hasattr(self, "_discord_channel_input") else "",
        }
        self._save_discord_settings(settings)
        self.discord_config_changed.emit(dict(settings))
        self._refresh_discord_card()

    def _refresh_discord_card(self, note: str = ""):
        if not hasattr(self, "_discord_status_lbl"):
            return
        token = self._discord_token_input.text().strip() if hasattr(self, "_discord_token_input") else ""
        enabled = bool(getattr(self, "_discord_enabled", False))
        if note:
            status = note
            color = C.PRI if "error" in note.lower() or "missing" in note.lower() else C.TEXT_MED
        elif not token:
            status = "Token required"
            color = C.PRI
        elif enabled:
            status = "Bot enabled"
            color = C.GREEN
        else:
            status = "Bot disabled"
            color = C.TEXT_MED
        self._discord_status_lbl.setText(status)
        self._discord_status_lbl.setStyleSheet(f"color: {color}; background: transparent;")
        if hasattr(self, "_discord_start_btn"):
            self._discord_start_btn.setEnabled(True)
        if hasattr(self, "_discord_stop_btn"):
            self._discord_stop_btn.setEnabled(True)
        if hasattr(self, "_discord_save_btn"):
            self._discord_save_btn.setText("Save Settings")

    def _startup_animation_enabled(self) -> bool:
        if platform.system() != "Windows":
            return False
        return bool(self._load_app_settings().get("startup_animation_enabled", True))

    def _set_startup_animation_enabled(self, enabled: bool) -> bool:
        try:
            settings = self._load_app_settings()
            settings["startup_animation_enabled"] = bool(enabled)
            settings["last_boot_stamp"] = _current_boot_stamp()
            self._save_app_settings(settings)
            return True
        except Exception as e:
            self._log.append_log(f"ERR: startup animation setting failed: {e}")
            return False

    def _refresh_startup_animation_button(self):
        if not hasattr(self, "_startup_anim_btn"):
            return
        if platform.system() != "Windows":
            self._startup_anim_btn.setText("Startup Animation (Windows only)")
            self._startup_anim_btn.setEnabled(False)
            return
        if self._startup_animation_enabled():
            self._startup_anim_btn.setText("Disable Startup Animation")
        else:
            self._startup_anim_btn.setText("Enable Startup Animation")

    def _toggle_startup_animation(self):
        if platform.system() != "Windows":
            return
        enabled = not self._startup_animation_enabled()
        if self._set_startup_animation_enabled(enabled):
            self._refresh_startup_animation_button()
            state = "enabled" if enabled else "disabled"
            self._log.append_log(f"SYS: Startup animation {state}.")

    def _should_play_boot_sequence(self) -> bool:
        if platform.system() != "Windows":
            return False
        if not _launched_from_windows_startup():
            return False
        if not self._win._startup_enabled():
            return False
        if not self._startup_animation_enabled():
            return False
        settings = self._load_app_settings()
        boot_stamp = _current_boot_stamp()
        last_boot = int(settings.get("last_boot_stamp") or 0)
        played = bool(settings.get("boot_sequence_played"))
        if last_boot != boot_stamp:
            settings["last_boot_stamp"] = boot_stamp
            settings["boot_sequence_played"] = False
            self._save_app_settings(settings)
            played = False
        return not played

    def _mark_boot_sequence_played(self):
        try:
            settings = self._load_app_settings()
            settings["last_boot_stamp"] = _current_boot_stamp()
            settings["boot_sequence_played"] = True
            self._save_app_settings(settings)
        except Exception:
            pass

    def play_boot_sequence(self, finished_callback=None):
        if self._boot_overlay is not None:
            try:
                self._boot_overlay.deleteLater()
            except Exception:
                pass
            self._boot_overlay = None
        self.hide_main()
        overlay = BootSequenceOverlay()
        self._boot_overlay = overlay

        device_name = platform.node() or os.environ.get("COMPUTERNAME") or "DEVICE"

        def _done():
            self._mark_boot_sequence_played()
            try:
                self.show_main()
            finally:
                if self._boot_overlay is not None:
                    try:
                        self._boot_overlay.deleteLater()
                    except Exception:
                        pass
                    self._boot_overlay = None
                if finished_callback:
                    finished_callback()

        overlay.finished.connect(_done)
        overlay.start(device_name=device_name, greeting_name="Suryaansh")

    # Thread-safe helpers for driving the boot overlay from background threads
    def boot_add_step(self, text: str):
        try:
            if not self._boot_overlay:
                return None
            QTimer.singleShot(0, lambda: self._boot_overlay.add_step(text))
        except Exception:
            pass

    def boot_set_step_status(self, text: str, status: str):
        try:
            if not self._boot_overlay:
                return
            QTimer.singleShot(0, lambda: self._boot_overlay.set_step_status(text, status))
        except Exception:
            pass

    def boot_set_progress(self, percent: int, tip: str | None = None):
        try:
            if not self._boot_overlay:
                return
            QTimer.singleShot(0, lambda: self._boot_overlay.set_progress(percent, tip))
        except Exception:
            pass

    def _build_tray_menu(self) -> QMenu:
        menu = QMenu()
        menu.setStyleSheet(f"""
            QMenu {{
                background: rgba(8, 8, 8, 245);
                color: {C.WHITE};
                border: 1px solid {C.BORDER_B};
                border-radius: 10px;
                padding: 6px;
            }}
            QMenu::item {{
                padding: 8px 18px;
                border-radius: 6px;
            }}
            QMenu::item:selected {{
                background: rgba(255,255,255,0.08);
            }}
        """)

        open_app_action = menu.addAction("Open App")
        open_action = menu.addAction("Open Workspace")
        close_action = menu.addAction("Close Workspace")
        startup_action = menu.addAction("Show Workspace On Startup")
        startup_action.setCheckable(True)
        startup_action.setChecked(bool(self._load_app_settings().get("show_workspace_on_startup", False)))
        show_icon_action = menu.addAction("Show Floating Icon")
        hide_icon_action = menu.addAction("Hide Floating Icon")
        menu.addSeparator()
        restart_action = menu.addAction("Restart")
        quit_action = menu.addAction("Quit")

        open_app_action.triggered.connect(self.show_main)
        open_action.triggered.connect(self._show_workspace_sidebar)
        close_action.triggered.connect(self._close_workspace_sidebar)
        startup_action.triggered.connect(lambda: self._toggle_workspace_on_startup(startup_action.isChecked()))
        show_icon_action.triggered.connect(self._show_floating_icon)
        hide_icon_action.triggered.connect(self._hide_launcher_with_protection)
        restart_action.triggered.connect(self._restart_app)
        quit_action.triggered.connect(self._app.quit)
        return menu

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_command_bar()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_control_panel()

    def _on_minimized(self):
        if self._launcher.isVisible():
            self._launcher.raise_()
        self._command_bar.hide()

    def _toggle_command_bar(self):
        if self._command_bar.isVisible():
            self._command_bar.hide()
        else:
            self._command_bar.show_near(self._launcher)

    def _toggle_workspace_sidebar(self):
        if self._workspace_sidebar.isVisible():
            self._close_workspace_sidebar()
        else:
            self._show_workspace_sidebar()

    def _show_workspace_sidebar(self):
        self._workspace_sidebar.show_workspace()
        self._launcher.hide()

    def _close_workspace_sidebar(self):
        self._workspace_sidebar.hide_workspace()
        self._show_floating_icon()

    def _show_floating_icon(self):
        launcher_pos = self._load_app_settings().get("launcher_pos")
        if isinstance(launcher_pos, (list, tuple)) and len(launcher_pos) == 2:
            try:
                self._launcher.show_at(int(launcher_pos[0]), int(launcher_pos[1]))
                return
            except Exception:
                pass
        self._launcher.show_at()

    def _restart_app(self):
        try:
            args = _hidden_launch_args("--startup" if _launched_from_windows_startup() else "")
            args = [arg for arg in args if arg]
            kwargs = {"cwd": str(BASE_DIR)}
            if _OS == "Windows":
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.Popen(args, **kwargs)
        except Exception as exc:
            self._win.write_log(f"ERR: Restart failed: {exc}")
        self._app.quit()

    def _toggle_workspace_on_startup(self, enabled: bool):
        try:
            settings = self._load_app_settings()
            settings["show_workspace_on_startup"] = bool(enabled)
            self._save_app_settings(settings)
        except Exception:
            pass

    def _hide_launcher_with_protection(self):
        self._show_hide_launcher_confirm()

    def _show_hide_launcher_confirm(self):
        panel = LauncherControlPanel(
            startup_workspace=bool(self._load_app_settings().get("show_workspace_on_startup", False)),
            on_open=self._show_workspace_sidebar,
            on_close=self._close_workspace_sidebar,
            on_toggle_startup=self._toggle_workspace_on_startup,
            on_hide_icon=self._launcher.hide,
            on_restart=self._restart_app,
            on_quit=self._app.quit,
            on_open_app=self.show_main,
            on_show_icon=self._show_floating_icon,
        )
        self._control_panel = panel
        self._position_control_panel(panel)
        panel.show()
        panel.raise_()
        panel.activateWindow()

    def _position_control_panel(self, panel: LauncherControlPanel):
        try:
            geo = self._launcher.geometry()
            panel.adjustSize()
            panel.move(max(20, geo.left() - panel.width() - 16), max(20, geo.top() - 10))
        except Exception:
            screen = QApplication.primaryScreen().availableGeometry()
            panel.move(screen.center().x() - panel.width() // 2, screen.center().y() - panel.height() // 2)

    def _show_control_panel(self):
        self._show_hide_launcher_confirm()

    def _handle_launcher_action(self, action: str):
        action = (action or "").strip().lower()
        if action == "open_app":
            self.show_main()
        elif action == "open_workspace":
            self._show_workspace_sidebar()
        elif action == "close_workspace":
            self._close_workspace_sidebar()
        elif action == "show_icon":
            self._show_floating_icon()
        elif action == "hide_icon":
            self._hide_launcher_with_protection()
        elif action == "restart":
            self._restart_app()
        elif action == "quit":
            self._app.quit()
        elif action == "toggle_startup":
            current = bool(self._load_app_settings().get("show_workspace_on_startup", False))
            self._toggle_workspace_on_startup(not current)

    def _submit_command(self, text: str):
        self._win.submit_command(text)

    def _browse_attachment(self):
        self._win._browse_attachment()

    def _toggle_mute(self):
        self._win._toggle_mute()

    def _on_chat_event(self, event: dict):
        try:
            self._discord_service.mirror_chat_event(event or {})
        except Exception:
            pass
        try:
            self._workspace_sidebar.record_chat_event(event or {})
        except Exception:
            pass
        try:
            self._win._inline_workspace.record_chat_event(event or {})
        except Exception:
            pass

    def _on_discord_config_changed(self, settings: dict):
        settings = settings or {}
        enabled = bool(settings.get("enabled", False) or (settings.get("bot_token") or "").strip())
        token = (settings.get("bot_token") or "").strip()
        channel_id = (settings.get("channel_id") or "").strip()
        self._discord_service.set_target_channel_id(channel_id)
        if not enabled or not token:
            self._discord_service.stop()
            if not token:
                self._win.discord_status_changed.emit("Token required")
            else:
                self._win.discord_status_changed.emit("Discord bot disabled")
            return
        try:
            self._discord_service.start(token)
        except Exception as exc:
            msg = f"Discord error: {exc}"
            self._win.discord_status_changed.emit(msg)
            self._win._log_sig.emit(f"ERR: {msg}")

    def _open_app(self):
        self._command_bar.hide()
        self._launcher.show_at()
        self._win.show_app()

    @property
    def muted(self) -> bool:
        return self._win._muted

    @muted.setter
    def muted(self, v: bool):
        if v != self._win._muted:
            self._win._toggle_mute()

    def set_muted(self, muted: bool):
        if bool(muted) != self._win._muted:
            self._win.set_muted_state(bool(muted))

    def set_muted_state(self, muted: bool, *, wakeword: bool = False):
        self._win.set_muted_state(bool(muted), wakeword=wakeword)

    @property
    def current_file(self) -> str | None:
        return self._win._current_file

    @property
    def on_text_command(self):
        return self._win.on_text_command

    @on_text_command.setter
    def on_text_command(self, cb):
        self._win.on_text_command = cb

    @property
    def on_remote_clicked(self):
        return self._win.on_remote_clicked

    @on_remote_clicked.setter
    def on_remote_clicked(self, cb):
        self._win.on_remote_clicked = cb

    @property
    def on_attention_action(self):
        return self._win.on_attention_action

    @on_attention_action.setter
    def on_attention_action(self, cb):
        self._win.on_attention_action = cb

    @property
    def on_chat_event(self):
        return self._win.on_chat_event

    @on_chat_event.setter
    def on_chat_event(self, cb):
        self._win.on_chat_event = cb

    def set_state(self, state: str):
        self._win._state_sig.emit(state)

    def write_log(self, text: str):
        self._win._log_sig.emit(text)

    def submit_external_command(self, text: str, source: str = "discord"):
        self._win.submit_command(text, source=source)

    def notify_phone_connected(self):
        self._win.notify_phone_connected()

    def set_scanning(self, enabled: bool, text: str = ""):
        self._win.set_scanning(enabled, text)

    def show_attention_alert(self, event: dict):
        self._win._attention_sig.emit(event or {})

    def set_meeting_mode(self, enabled: bool, title: str = "", summary: str = "", answer: str = "", speech: str = ""):
        self._win.set_meeting_mode(enabled, title, summary, answer, speech)

    def begin_task_workspace(self, command: str, plan: list[str] | str | None = None, source: str = "local"):
        self._win._task_workspace_sig.emit({
            "action": "start",
            "command": command or "",
            "plan": plan or [],
            "source": source or "local",
        })

    def update_task_workspace(self, *, title: str | None = None, command: str | None = None, plan: list[str] | str | None = None,
                              status: str | None = None, output: str | None = None, percent: int | None = None,
                              footer: str | None = None, source: str | None = None):
        payload = {"action": "update"}
        if title is not None:
            payload["title"] = title
        if command is not None:
            payload["command"] = command
        if plan is not None:
            payload["plan"] = plan
        if status is not None:
            payload["status"] = status
        if output is not None:
            payload["output"] = output
        if percent is not None:
            payload["percent"] = percent
        if footer is not None:
            payload["footer"] = footer
        if source is not None:
            payload["source"] = source or "local"
        self._win._task_workspace_sig.emit(payload)

    def finish_task_workspace(self, result: str, status: str = "Task completed.", percent: int = 100):
        self._win._task_workspace_sig.emit({
            "action": "finish",
            "result": result or "Done.",
            "status": status or "Task completed.",
            "percent": percent,
        })

    def clear_task_workspace(self):
        self._win._task_workspace_sig.emit({"action": "clear"})

    def wait_for_api_key(self):
        while not self._win._ready:
            time.sleep(0.1)

    def start_speaking(self):
        self.set_state("SPEAKING")

    def stop_speaking(self):
        if not self.muted:
            self.set_state("LISTENING")





