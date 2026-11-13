# -*- coding: utf-8 -*-
"""桌面备忘录 —— PySide6 原生客户端（玻璃圆角卡片风格）"""
import os
import sys
import json
import time
import random
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Signal, QPoint, QRectF, QSize, QEvent
from PySide6.QtGui import QColor, QPixmap, QPainter, QBrush, QPainterPath, QCursor, QIcon, QPen
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPlainTextEdit, QPushButton, QScrollArea, QLabel, QFrame, QCheckBox,
    QColorDialog, QFileDialog, QMessageBox, QDialog, QListWidget, QListWidgetItem,
    QToolButton, QStyle, QGraphicsDropShadowEffect, QSizePolicy
)

# ============ 常量与持久化 ============
APP_NAME = "DesktopMemo"
APP_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), APP_NAME)
DATA_FILE = os.path.join(APP_DIR, "data.json")
CACHE_DIR = os.path.join(APP_DIR, "cache")

PRESET_COLORS = ["#F6C85F", "#E8826D", "#7FB77E", "#7FA8D9", "#B59AD6",
                 "#E7A6B8", "#8FC7C2", "#D9A05B"]
DONE_IDLE = 5 * 60          # 完成后 5 分钟无操作自动归档
OVERDUE = 24 * 60 * 60      # 超过 24 小时未完成提醒
MIN_W, MIN_H = 320, 380
RADIUS = 20


def _app_icon():
    """加载应用图标（开发态取源码目录，打包态取 _MEIPASS）。"""
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.ico"),
        os.path.join(getattr(sys, "_MEIPASS", "") or "", "logo.ico"),
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return QIcon(c)
    return QIcon()
RESIZE_M = 14
ICON_COLOR = "#5A564E"


def now_ts():
    return time.time()


def fmt_time(ts):
    if not ts:
        return ""
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def uid():
    return datetime.now().strftime("%Y%m%d%H%M%S%f") + str(random.randint(100, 999))


def normalize_task(t):
    t.setdefault("title", "")
    t.setdefault("note", "")
    t.setdefault("color", "#F6C85F")
    t.setdefault("pinned", False)
    t.setdefault("done", False)
    t.setdefault("createdAt", now_ts())
    t.setdefault("completedAt", None)
    t.setdefault("lastActionAt", t["createdAt"])
    t.setdefault("reminded", False)
    t.setdefault("archivedAt", None)
    return t


def default_data():
    return {
        "tasks": [],
        "history": [],
        "settings": {
            "dark": False, "bgType": "color", "bgColor": "#F1EEE9", "bgImage": "",
            "locked": False, "pos": None, "alwaysOnTop": False, "lastCleanup": None,
        },
    }


def load_data():
    data = default_data()
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            for k, v in data.items():
                loaded.setdefault(k, v)
            for k, v in data["settings"].items():
                loaded["settings"].setdefault(k, v)
            data = loaded
    except Exception:
        pass
    data["tasks"] = [normalize_task(t) for t in data["tasks"]]
    data["history"] = [normalize_task(t) for t in data["history"]]
    return data


def save_data(data):
    os.makedirs(APP_DIR, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def clear_cache(silent=False):
    os.makedirs(CACHE_DIR, exist_ok=True)
    for name in os.listdir(CACHE_DIR):
        try:
            os.remove(os.path.join(CACHE_DIR, name))
        except OSError:
            pass
    if not silent:
        QMessageBox.information(None, "缓存", "缓存已清理")


def last_sunday_midnight(now):
    d = datetime.fromtimestamp(now).replace(hour=0, minute=0, second=0, microsecond=0)
    sub = 0 if d.weekday() == 6 else d.weekday() + 1
    return datetime.fromordinal(d.toordinal() - sub).timestamp()


# ============ 矢量图标 ============
SVG_ICONS = {
    "lock": "锁定.svg",
    "pin": "钉住1.svg",
    "moon": "深色.svg",
    "pencil": "编辑.svg",
    "gear": "设置.svg",
    "trash": "删除.svg",
    "clock": "历史记录.svg",
}


def _icon_svg_path(name):
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons", name),
        os.path.join(getattr(sys, "_MEIPASS", "") or "", "icons", name),
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return ""


def _render_svg(path, size, color):
    renderer = QSvgRenderer(path)
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    renderer.render(p)
    p.end()
    # 保留 alpha，按当前主题色重新着色
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setCompositionMode(QPainter.CompositionMode_SourceIn)
    p.fillRect(pm.rect(), QColor(color))
    p.end()
    return pm


def _icon_pixmap(kind, size=20, color="#5A564E"):
    c = QColor(color)
    if kind in SVG_ICONS:
        path = _icon_svg_path(SVG_ICONS[kind])
        if path:
            return _render_svg(path, size, color)
    # 兜底手绘：锁
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    u = size / 20.0
    p.setPen(QPen(c, 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)

    def R(x, y, w, h):
        return QRectF(x * u, y * u, w * u, h * u)

    if kind == "lock":
        p.drawArc(R(7, 5, 6, 5.5), 180 * 16, -180 * 16)
        p.drawRoundedRect(R(5.5, 10, 9, 6.5), 1.6 * u, 1.6 * u)
    p.end()
    return pm


# ============ 背景容器（圆角裁切） ============
class BgWidget(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = self.settings
        base = QColor(s["bgColor"])
        if s["dark"] and s["bgColor"] == "#F1EEE9":
            base = QColor("#1B1B1F")

        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), RADIUS, RADIUS)
        p.setClipPath(path)
        p.fillRect(self.rect(), QBrush(base))

        if s["bgType"] == "image" and s["bgImage"] and os.path.exists(s["bgImage"]):
            pix = QPixmap(s["bgImage"])
            if not pix.isNull():
                pix = pix.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                x = (self.width() - pix.width()) // 2
                y = (self.height() - pix.height()) // 2
                p.setOpacity(0.5 if not s["dark"] else 0.32)
                p.drawPixmap(x, y, pix)
        p.end()


# ============ 任务卡片 ============
class TaskCard(QFrame):
    changed = Signal()
    deleteRequested = Signal(object)

    def __init__(self, task, parent=None):
        super().__init__(parent)
        self.task = normalize_task(task)
        self.build_ui()
        self.refresh()

    def build_ui(self):
        self.setObjectName("taskCard")
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 11, 10, 11)
        root.setSpacing(10)

        self.check = QCheckBox()
        self.check.setChecked(self.task["done"])
        self.check.stateChanged.connect(self.on_done)
        root.addWidget(self.check, 0, Qt.AlignTop)

        mid = QVBoxLayout()
        mid.setSpacing(4)
        self.title = QLabel(self.task["title"])
        self.title.setWordWrap(True)
        tf = self.title.font()
        tf.setBold(True)
        tf.setPointSize(10.5)
        self.title.setFont(tf)
        mid.addWidget(self.title)

        self.note_label = QLabel(self.task["note"])
        self.note_label.setWordWrap(True)
        self.note_label.setProperty("muted", True)
        mid.addWidget(self.note_label)

        self.note_editor = QPlainTextEdit()
        self.note_editor.setPlaceholderText("备注")
        self.note_editor.setFixedHeight(56)
        self.note_editor.hide()
        self.note_save = QPushButton("保存备注")
        self.note_save.setObjectName("ghost")
        self.note_save.clicked.connect(self.save_note)
        self.note_save.hide()
        mid.addWidget(self.note_editor)
        mid.addWidget(self.note_save)

        self.meta = QLabel()
        self.meta.setProperty("muted", True)
        mid.addWidget(self.meta)
        root.addLayout(mid, 1)

        self.pin_btn = self._icon_btn("pin", "置顶", self.on_pin, checkable=True)
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(18, 18)
        self.color_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.color_btn.setToolTip("修改颜色")
        self.color_btn.setCursor(Qt.PointingHandCursor)
        self.color_btn.clicked.connect(self.pick_color)
        self.note_btn = self._icon_btn("pencil", "编辑备注", self.edit_note)
        self.del_btn = self._icon_btn("trash", "删除任务",
                                      lambda: self.deleteRequested.emit(self.task), danger=True)

        side = QVBoxLayout()
        side.setSpacing(2)
        side_top = QHBoxLayout()
        side_top.setSpacing(6)
        side_top.addWidget(self.pin_btn)
        side_top.addWidget(self.color_btn, 0, Qt.AlignTop)
        side.addLayout(side_top)
        side.addWidget(self.note_btn)
        side.addWidget(self.del_btn)
        root.addLayout(side, 0)

    def _icon_btn(self, kind, tip, slot, checkable=False, danger=False):
        b = QPushButton()
        b.setCheckable(checkable)
        b.setFlat(True)
        b.setFixedSize(28, 28)
        b.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        b.setIconSize(QSize(18, 18))
        b.setToolTip(tip)
        b.setCursor(Qt.PointingHandCursor)
        if danger:
            b.setProperty("danger", True)
        b.clicked.connect(slot)
        b._icon_kind = kind
        self._refresh_card_icon(b)
        return b

    def _refresh_card_icon(self, b):
        b.setIcon(QIcon(_icon_pixmap(b._icon_kind, 18, ICON_COLOR)))

    def touch(self):
        self.task["lastActionAt"] = now_ts()

    def on_done(self, _state):
        self.task["done"] = self.check.isChecked()
        now = now_ts()
        if self.task["done"]:
            self.task["completedAt"] = now
            self.task["reminded"] = True
        else:
            self.task["completedAt"] = None
        self.touch()
        self.refresh()
        self.changed.emit()

    def on_pin(self, checked):
        self.task["pinned"] = checked
        self.touch()
        self.changed.emit()

    def edit_note(self):
        self.note_editor.setPlainText(self.task["note"])
        self.note_label.hide()
        self.note_editor.show()
        self.note_save.show()
        self.note_editor.setFocus()

    def save_note(self):
        self.task["note"] = self.note_editor.toPlainText().strip()
        self.touch()
        self.note_label.setText(self.task["note"])
        self.note_label.setVisible(bool(self.task["note"]))
        self.note_editor.hide()
        self.note_save.hide()
        self.refresh()
        self.changed.emit()

    def pick_color(self):
        col = QColorDialog.getColor(QColor(self.task["color"]), self, "选择任务颜色")
        if col.isValid():
            self.task["color"] = col.name()
            self.touch()
            self.refresh()
            self.changed.emit()

    def refresh(self):
        t = self.task
        self.title.setText(t["title"])
        fmt = self.title.font()
        fmt.setStrikeOut(t["done"])
        self.title.setFont(fmt)
        self.note_label.setText(t["note"])
        self.note_label.setVisible(bool(t["note"]) and not self.note_editor.isVisible())
        self.pin_btn.setChecked(t["pinned"])
        self.color_btn.setStyleSheet(
            "background:%s;border-radius:4px;border:1px solid rgba(0,0,0,.18);" % t["color"])
        for b in (self.pin_btn, self.note_btn, self.del_btn):
            self._refresh_card_icon(b)
        c = QColor(t["color"])
        tint = QColor(c)
        tint.setAlpha(24)
        self.setStyleSheet(
            "#taskCard{border:1px solid rgba(120,115,105,.28);"
            "border-left:3px solid %s;border-radius:14px;background:%s;}"
            % (t["color"], tint.name(QColor.HexArgb))
        )
        self.update_meta(now_ts())

    def update_meta(self, now):
        t = self.task
        parts = ["创建于 " + fmt_time(t["createdAt"])]
        overdue = False
        if t["done"]:
            base = t.get("lastActionAt") or t.get("completedAt") or t["createdAt"]
            remain = max(0, DONE_IDLE - (now - base))
            parts.append("%d:%02d 后自动归档" % (remain // 60, remain % 60))
        elif now - t["createdAt"] > OVERDUE:
            parts.append("已超 24 小时")
            overdue = True
        self.meta.setText(" · ".join(parts))
        self.meta.setStyleSheet("color:#C4574B;" if overdue else "")


# ============ 历史对话框 ============
class HistoryDialog(QDialog):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.data = data
        self.setWindowTitle("历史任务")
        self.resize(380, 440)
        lay = QVBoxLayout(self)
        hint = QLabel("完成后自动消失的任务存放在这里；历史任务每周日 00:00 自动清空并清理缓存。")
        hint.setWordWrap(True)
        hint.setProperty("muted", True)
        lay.addWidget(hint)
        self.list = QListWidget()
        lay.addWidget(self.list, 1)
        row = QHBoxLayout()
        self.clear_btn = QPushButton("清空历史任务")
        self.clear_btn.setObjectName("ghost")
        self.clear_btn.clicked.connect(self.clear_all)
        row.addStretch()
        row.addWidget(self.clear_btn)
        lay.addLayout(row)
        self.reload()

    def reload(self):
        self.list.clear()
        for h in self.data["history"]:
            text = h["title"] + "\n创建于 " + fmt_time(h["createdAt"]) + \
                   " · 归档于 " + fmt_time(h.get("archivedAt"))
            if h.get("note"):
                text += "\n备注：" + h["note"]
            self.list.addItem(QListWidgetItem(text))

    def clear_all(self):
        self.data["history"] = []
        save_data(self.data)
        self.reload()


# ============ 设置对话框 ============
class SettingsDialog(QDialog):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.main = main
        self.s = main.settings
        self.setWindowTitle("设置")
        self.resize(360, 430)
        lay = QVBoxLayout(self)
        lay.setSpacing(12)

        row = QHBoxLayout()
        row.addWidget(QLabel("背景颜色"))
        self.bg_color_btn = QPushButton()
        self.bg_color_btn.setFixedSize(42, 28)
        self.bg_color_btn.setStyleSheet("border-radius:8px;")
        self.bg_color_btn.clicked.connect(self.pick_bg_color)
        row.addStretch()
        row.addWidget(self.bg_color_btn)
        lay.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("背景图片"))
        self.bg_img_btn = QPushButton("选择图片")
        self.bg_img_btn.setObjectName("ghost")
        self.bg_img_btn.clicked.connect(self.pick_bg_image)
        self.bg_remove = QPushButton("移除")
        self.bg_remove.setObjectName("ghost")
        self.bg_remove.clicked.connect(self.remove_bg_image)
        row.addStretch()
        row.addWidget(self.bg_img_btn)
        row.addWidget(self.bg_remove)
        lay.addLayout(row)

        self.dark_chk = QCheckBox("深色模式")
        self.dark_chk.setChecked(self.s["dark"])
        self.lock_chk = QCheckBox("锁定窗口位置")
        self.lock_chk.setChecked(self.s["locked"])
        self.top_chk = QCheckBox("窗口始终置顶")
        self.top_chk.setChecked(self.s["alwaysOnTop"])
        lay.addWidget(self.dark_chk)
        lay.addWidget(self.lock_chk)
        lay.addWidget(self.top_chk)

        row = QHBoxLayout()
        self.cache_btn = QPushButton("立即清理缓存")
        self.cache_btn.setObjectName("ghost")
        self.cache_btn.clicked.connect(lambda: clear_cache())
        row.addStretch()
        row.addWidget(self.cache_btn)
        lay.addLayout(row)
        lay.addStretch()

        self.sync_color_btn()
        self.dark_chk.toggled.connect(self.on_dark)
        self.lock_chk.toggled.connect(lambda v: self._save(locked=v))
        self.top_chk.toggled.connect(self.on_top)

    def _save(self, **kw):
        self.s.update(kw)
        save_data(self.main.data)

    def sync_color_btn(self):
        self.bg_color_btn.setStyleSheet("background:%s;border-radius:8px;" % self.s["bgColor"])

    def pick_bg_color(self):
        col = QColorDialog.getColor(QColor(self.s["bgColor"]), self, "背景颜色")
        if col.isValid():
            self.s["bgColor"] = col.name()
            self.s["bgType"] = "color"
            self.sync_color_btn()
            save_data(self.main.data)
            self.main.refresh_bg()

    def pick_bg_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择背景图片", "",
                                               "图片 (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path:
            self.s["bgImage"] = path
            self.s["bgType"] = "image"
            save_data(self.main.data)
            self.main.refresh_bg()

    def remove_bg_image(self):
        self.s["bgImage"] = ""
        self.s["bgType"] = "color"
        save_data(self.main.data)
        self.main.refresh_bg()

    def on_dark(self, v):
        self.s["dark"] = v
        save_data(self.main.data)
        self.main.apply_theme()

    def on_top(self, v):
        self.s["alwaysOnTop"] = v
        save_data(self.main.data)
        self.main.apply_top_flag()


# ============ 主题样式 ============
LIGHT_QSS = """
QWidget{color:#26241F;font-family:"Microsoft YaHei","PingFang SC",sans-serif;font-size:13px;}
#panel{background:rgba(255,255,255,.82);border-radius:20px;border:1px solid rgba(38,36,31,.12);}
QLineEdit,QPlainTextEdit{background:rgba(38,36,31,.05);border:1px solid rgba(38,36,31,.12);border-radius:12px;padding:9px 11px;selection-background-color:#4C6E91;}
QLineEdit:focus,QPlainTextEdit:focus{border-color:#4C6E91;background:#FFFFFF;}
QPushButton#primary{background:#4C6E91;color:white;border-radius:12px;padding:8px 18px;font-weight:500;}
QPushButton#primary:hover{background:#5A7DA3;}
QPushButton#ghost{border:1px solid rgba(38,36,31,.12);border-radius:12px;padding:8px 14px;color:#6B665C;}
QPushButton#ghost:hover{background:rgba(38,36,31,.06);color:#26241F;}
QPushButton{border-radius:9px;padding:5px 8px;background:none;border:none;}
QPushButton:hover{background:rgba(38,36,31,.06);}
QPushButton:checked{color:#4C6E91;background:rgba(76,110,145,.12);}
QPushButton[danger="true"]:hover{color:#C4574B;}
QCheckBox{spacing:6px;}
QListWidget{background:rgba(38,36,31,.05);border:1px solid rgba(38,36,31,.1);border-radius:14px;}
QLabel[muted="true"]{color:#6B665C;font-size:12px;}
QScrollArea{border:none;background:transparent;}
#listHost{background:transparent;}
"""

DARK_QSS = """
QWidget{color:#E9E7E1;font-family:"Microsoft YaHei","PingFang SC",sans-serif;font-size:13px;}
#panel{background:rgba(34,34,39,.88);border-radius:20px;border:1px solid rgba(233,231,225,.14);}
QLineEdit,QPlainTextEdit{background:rgba(233,231,225,.07);border:1px solid rgba(233,231,225,.16);border-radius:12px;padding:9px 11px;selection-background-color:#7FA8D9;}
QLineEdit:focus,QPlainTextEdit:focus{border-color:#7FA8D9;background:#26262C;}
QPushButton#primary{background:#7FA8D9;color:#1B1B1F;border-radius:12px;padding:8px 18px;font-weight:500;}
QPushButton#primary:hover{background:#8FB6E3;}
QPushButton#ghost{border:1px solid rgba(233,231,225,.16);border-radius:12px;padding:8px 14px;color:#A29E93;}
QPushButton#ghost:hover{background:rgba(233,231,225,.08);color:#E9E7E1;}
QPushButton{border-radius:9px;padding:5px 8px;background:none;border:none;}
QPushButton:hover{background:rgba(233,231,225,.08);}
QPushButton:checked{color:#7FA8D9;background:rgba(127,168,217,.16);}
QPushButton[danger="true"]:hover{color:#E08A7E;}
QCheckBox{spacing:6px;}
QListWidget{background:rgba(233,231,225,.06);border:1px solid rgba(233,231,225,.12);border-radius:14px;}
QLabel[muted="true"]{color:#A29E93;font-size:12px;}
QScrollArea{border:none;background:transparent;}
#listHost{background:transparent;}
"""


# ============ 主窗口 ============
class MainWindow(QMainWindow):
    def __init__(self, data):
        super().__init__()
        self.data = data
        self.settings = data["settings"]
        self.drag_pos = None
        self.resize_mode = None
        self.resize_start_geom = None
        self.resize_start_global = None
        self.form_color = "#F6C85F"

        self.setWindowTitle("桌面备忘录")
        self.setWindowIcon(_app_icon())
        self.resize(480, 600)
        self.setMinimumSize(MIN_W, MIN_H)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        self.build_ui()
        self.apply_theme()
        self.restore_window()
        self.rebuild_tasks()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(1000)
        self.tick()

    # ---- 界面搭建 ----
    def build_ui(self):
        central = BgWidget(self.settings)
        self.setCentralWidget(central)
        central.setMouseTracking(True)
        central.installEventFilter(self)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        panel = QFrame()
        panel.setObjectName("panel")
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(34)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 52))
        panel.setGraphicsEffect(shadow)
        root.addWidget(panel)

        pl = QVBoxLayout(panel)
        pl.setContentsMargins(16, 14, 16, 14)
        pl.setSpacing(12)

        bar = QHBoxLayout()
        bar.setSpacing(6)
        grip = QLabel("···")
        grip.setProperty("muted", True)
        bar.addWidget(grip)
        self.title_label = QLabel("备忘录")
        tf = self.title_label.font()
        tf.setBold(True)
        tf.setPointSize(13)
        self.title_label.setFont(tf)
        bar.addWidget(self.title_label)
        bar.addStretch()

        self.btn_lock = self._tool_btn("lock", "锁定位置", self.toggle_lock, checkable=True)
        self.btn_top = self._tool_btn("pin", "窗口置顶", self.toggle_top, checkable=True)
        self.btn_dark = self._tool_btn("moon", "深色模式", self.toggle_dark, checkable=True)
        self.btn_hist = self._tool_btn("clock", "历史任务", self.open_history)
        self.btn_set = self._tool_btn("gear", "设置", self.open_settings)
        self.btn_min = QToolButton()
        self.btn_min.setFixedSize(32, 32)
        self.btn_min.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btn_min.setIcon(self.style().standardIcon(QStyle.SP_TitleBarMinButton))
        self.btn_min.clicked.connect(self.showMinimized)
        self.btn_close = QToolButton()
        self.btn_close.setFixedSize(32, 32)
        self.btn_close.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btn_close.setIcon(self.style().standardIcon(QStyle.SP_TitleBarCloseButton))
        self.btn_close.clicked.connect(self.close)
        self.tool_btns = [self.btn_lock, self.btn_top, self.btn_dark, self.btn_hist, self.btn_set]
        for b in self.tool_btns + [self.btn_min, self.btn_close]:
            bar.addWidget(b)
        pl.addLayout(bar)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("添加新任务，回车保存")
        self.title_input.returnPressed.connect(self.add_task)
        self.note_input = QPlainTextEdit()
        self.note_input.setPlaceholderText("备注（可选）")
        self.note_input.setFixedHeight(54)
        pl.addWidget(self.title_input)
        pl.addWidget(self.note_input)

        swatch_row = QHBoxLayout()
        swatch_row.setSpacing(7)
        self.swatch_btns = []
        for color in PRESET_COLORS:
            b = QPushButton()
            b.setFixedSize(22, 22)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet("border-radius:11px;background:%s;border:1px solid rgba(0,0,0,.15);" % color)
            b.clicked.connect(lambda _=False, c=color: self.pick_preset(c))
            self.swatch_btns.append((b, color))
            swatch_row.addWidget(b)
        self.color_custom = QPushButton()
        self.color_custom.setFixedSize(22, 22)
        self.color_custom.setToolTip("自定义颜色")
        self.color_custom.clicked.connect(self.pick_form_color)
        swatch_row.addWidget(self.color_custom)
        swatch_row.addStretch()
        self.add_btn = QPushButton("添加")
        self.add_btn.setObjectName("primary")
        self.add_btn.clicked.connect(self.add_task)
        swatch_row.addWidget(self.add_btn)
        pl.addLayout(swatch_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_host = QWidget()
        self.list_host.setObjectName("listHost")
        self.list_layout = QVBoxLayout(self.list_host)
        self.list_layout.setSpacing(10)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.addStretch()
        scroll.setWidget(self.list_host)
        pl.addWidget(scroll, 1)

        self.empty_label = QLabel("暂无进行中的任务")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setProperty("muted", True)
        pl.addWidget(self.empty_label)

        footer = QHBoxLayout()
        self.count_label = QLabel()
        self.count_label.setProperty("muted", True)
        footer.addWidget(self.count_label)
        footer.addStretch()
        pl.addLayout(footer)

        self._refresh_swatch()

    def _tool_btn(self, kind, tip, slot, checkable=False):
        b = QPushButton()
        b.setCheckable(checkable)
        b.setFlat(True)
        b.setFixedSize(32, 32)
        b.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        b.setIconSize(QSize(20, 20))
        b.setToolTip(tip)
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(slot)
        b._icon_kind = kind
        self._tool_refresh(b)
        return b

    def _tool_refresh(self, b):
        b.setIcon(QIcon(_icon_pixmap(b._icon_kind, 20, ICON_COLOR)))

    def _refresh_swatch(self):
        for b, color in self.swatch_btns:
            ring = "border:2px solid #26241F;" if color == self.form_color else "border:1px solid rgba(0,0,0,.15);"
            b.setStyleSheet("border-radius:11px;background:%s;%s" % (color, ring))
        self.color_custom.setStyleSheet(
            "border-radius:11px;background:%s;border:1px dashed rgba(38,36,31,.35);" % self.form_color)

    # ---- 任务操作 ----
    def pick_preset(self, color):
        self.form_color = color
        self._refresh_swatch()

    def pick_form_color(self):
        col = QColorDialog.getColor(QColor(self.form_color), self, "选择颜色")
        if col.isValid():
            self.form_color = col.name()
            self._refresh_swatch()

    def add_task(self):
        title = self.title_input.text().strip()
        if not title:
            QMessageBox.warning(self, "提示", "请输入任务内容")
            return
        t = {
            "id": uid(), "title": title,
            "note": self.note_input.toPlainText().strip(),
            "color": self.form_color, "pinned": False, "done": False,
            "createdAt": now_ts(), "completedAt": None, "lastActionAt": now_ts(),
            "reminded": False, "archivedAt": None,
        }
        self.data["tasks"].append(t)
        self.title_input.clear()
        self.note_input.clear()
        save_data(self.data)
        self.rebuild_tasks()

    def rebuild_tasks(self):
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        ordered = sorted(self.data["tasks"],
                         key=lambda x: (not x["pinned"], -x["createdAt"]))
        for t in ordered:
            card = TaskCard(t)
            card.changed.connect(self.on_card_changed)
            card.deleteRequested.connect(self.on_card_delete)
            self.list_layout.insertWidget(self.list_layout.count() - 1, card)
        self.empty_label.setVisible(not ordered)
        self.refresh_counts()

    def on_card_changed(self):
        save_data(self.data)
        self.refresh_counts()

    def on_card_delete(self, task):
        self.data["tasks"] = [x for x in self.data["tasks"] if x["id"] != task["id"]]
        save_data(self.data)
        self.rebuild_tasks()

    def refresh_counts(self):
        active = sum(1 for t in self.data["tasks"] if not t["done"])
        self.count_label.setText("进行中 %d · 已归档 %d" % (active, len(self.data["history"])))

    # ---- 定时规则 ----
    def tick(self):
        now = now_ts()

        remain = []
        archived = False
        for t in self.data["tasks"]:
            base = t.get("lastActionAt") or t.get("completedAt") or t["createdAt"]
            if t["done"] and now - base >= DONE_IDLE:
                t["archivedAt"] = now
                self.data["history"].insert(0, t)
                archived = True
            else:
                remain.append(t)
        if archived:
            self.data["tasks"] = remain
            save_data(self.data)
            self.rebuild_tasks()

        newly = []
        for t in self.data["tasks"]:
            if not t["done"] and not t.get("reminded") and now - t["createdAt"] > OVERDUE:
                t["reminded"] = True
                t["pinned"] = True
                newly.append(t)
        if newly:
            save_data(self.data)
            self.rebuild_tasks()
            msg = "以下任务已超过 24 小时未完成，已自动置顶：\n\n" + \
                  "\n".join("· " + t["title"] for t in newly)
            QMessageBox.warning(self, "任务提醒", msg, QMessageBox.Ok)

        self.weekly_cleanup(now)

        for i in range(self.list_layout.count()):
            w = self.list_layout.itemAt(i).widget()
            if isinstance(w, TaskCard):
                w.update_meta(now)
        self.refresh_counts()

    def weekly_cleanup(self, now):
        s = self.settings
        if s.get("lastCleanup") is None:
            s["lastCleanup"] = now
            save_data(self.data)
            return
        if s["lastCleanup"] < last_sunday_midnight(now):
            self.data["history"] = []
            clear_cache(silent=True)
            s["lastCleanup"] = now
            save_data(self.data)

    # ---- 窗口与主题 ----
    def apply_theme(self):
        global ICON_COLOR
        ICON_COLOR = "#C9C6BE" if self.settings["dark"] else "#5A564E"
        QApplication.instance().setStyleSheet(DARK_QSS if self.settings["dark"] else LIGHT_QSS)
        self.refresh_bg()
        for b in self.tool_btns:
            self._tool_refresh(b)
        for i in range(self.list_layout.count()):
            w = self.list_layout.itemAt(i).widget()
            if isinstance(w, TaskCard):
                for bb in (w.pin_btn, w.note_btn, w.del_btn):
                    w._refresh_card_icon(bb)
        self.btn_dark.setChecked(self.settings["dark"])
        self.btn_lock.setChecked(self.settings["locked"])
        self.btn_top.setChecked(self.settings["alwaysOnTop"])

    def refresh_bg(self):
        self.centralWidget().update()

    def apply_top_flag(self):
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.settings["alwaysOnTop"])
        self.show()

    def toggle_lock(self, checked):
        self.settings["locked"] = checked
        save_data(self.data)

    def toggle_top(self, checked):
        self.settings["alwaysOnTop"] = checked
        self.apply_top_flag()
        save_data(self.data)

    def toggle_dark(self, checked):
        self.settings["dark"] = checked
        save_data(self.data)
        self.apply_theme()

    def open_history(self):
        dlg = HistoryDialog(self.data, self)
        dlg.exec()
        self.refresh_counts()

    def open_settings(self):
        dlg = SettingsDialog(self, self)
        dlg.exec()
        self.refresh_counts()

    def restore_window(self):
        if self.settings.get("alwaysOnTop"):
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        pos = self.settings.get("pos")
        if pos:
            self.move(pos[0], pos[1])
        self._clamp_to_screen()

    def _clamp_to_screen(self):
        screen = QApplication.screenAt(self.pos()) or QApplication.primaryScreen()
        avail = screen.availableGeometry()
        g = self.geometry()
        if g.width() > avail.width():
            g.setWidth(avail.width())
        if g.height() > avail.height():
            g.setHeight(avail.height())
        x = max(avail.left(), min(g.x(), avail.right() - g.width()))
        y = max(avail.top(), min(g.y(), avail.bottom() - g.height()))
        self.setGeometry(x, y, g.width(), g.height())

    def save_window_pos(self):
        self.settings["pos"] = [self.x(), self.y()]
        save_data(self.data)

    # ---- 无边框：拖拽移动 + 边缘缩放 ----
    def _edges(self, pos):
        e = set()
        r = self.rect()
        if pos.x() <= RESIZE_M:
            e.add("l")
        if pos.x() >= r.width() - RESIZE_M:
            e.add("r")
        if pos.y() <= RESIZE_M:
            e.add("t")
        if pos.y() >= r.height() - RESIZE_M:
            e.add("b")
        return e

    def _cursor_for(self, edges):
        if "l" in edges and "t" in edges:
            return Qt.SizeFDiagCursor
        if "r" in edges and "b" in edges:
            return Qt.SizeFDiagCursor
        if "r" in edges and "t" in edges:
            return Qt.SizeBDiagCursor
        if "l" in edges and "b" in edges:
            return Qt.SizeBDiagCursor
        if "l" in edges or "r" in edges:
            return Qt.SizeHorCursor
        if "t" in edges or "b" in edges:
            return Qt.SizeVerCursor
        return Qt.ArrowCursor

    # ---- 内部统一处理（Qt 事件与事件过滤器共用）----
    def _on_press(self, pos, gp, e):
        if e.button() != Qt.LeftButton:
            return
        edges = self._edges(pos)
        if edges and not self.settings["locked"]:
            self.resize_mode = edges
            self.resize_start_geom = self.geometry()
            self.resize_start_global = gp
            return
        if pos.y() <= 46 and not self.settings["locked"]:
            child = self.childAt(pos)
            if not isinstance(child, (QToolButton, QPushButton, QCheckBox)):
                self.drag_pos = gp - self.frameGeometry().topLeft()

    def _on_move(self, pos, gp, e):
        if self.resize_mode:
            g = self.resize_start_geom
            dx = gp.x() - self.resize_start_global.x()
            dy = gp.y() - self.resize_start_global.y()
            left, top, right, bottom = g.left(), g.top(), g.right(), g.bottom()
            if "l" in self.resize_mode:
                left = g.left() + dx
            if "r" in self.resize_mode:
                right = g.right() + dx
            if "t" in self.resize_mode:
                top = g.top() + dy
            if "b" in self.resize_mode:
                bottom = g.bottom() + dy
            if right - left < MIN_W:
                if "l" in self.resize_mode:
                    left = right - MIN_W
                else:
                    right = left + MIN_W
            if bottom - top < MIN_H:
                if "t" in self.resize_mode:
                    top = bottom - MIN_H
                else:
                    bottom = top + MIN_H
            self.setGeometry(left, top, right - left, bottom - top)
            return
        if self.drag_pos is not None and e.buttons() & Qt.LeftButton:
            self.move(gp - self.drag_pos)
            return
        self.setCursor(QCursor(self._cursor_for(self._edges(pos))))

    def _on_release(self, e):
        self.drag_pos = None
        self.resize_mode = None
        self.save_window_pos()

    def mousePressEvent(self, e):
        self._on_press(e.position().toPoint(), e.globalPosition().toPoint(), e)
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        self._on_move(e.position().toPoint(), e.globalPosition().toPoint(), e)
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._on_release(e)
        super().mouseReleaseEvent(e)

    def eventFilter(self, obj, event):
        t = event.type()
        if t in (QEvent.MouseButtonPress, QEvent.MouseMove, QEvent.MouseButtonRelease):
            win_pos = obj.mapTo(self, event.position().toPoint())
            gp = event.globalPosition().toPoint()
            if t == QEvent.MouseButtonPress:
                if self._edges(win_pos) and not self.settings["locked"]:
                    self._on_press(win_pos, gp, event)
                    return True
            elif t == QEvent.MouseMove:
                if self.resize_mode:
                    self._on_move(win_pos, gp, event)
                    return True
                if self._edges(win_pos):
                    self.setCursor(QCursor(self._cursor_for(self._edges(win_pos))))
                    return True
            else:
                if self.resize_mode or self.drag_pos:
                    self._on_release(event)
                    return True
        return super().eventFilter(obj, event)

    def closeEvent(self, e):
        self.save_window_pos()
        super().closeEvent(e)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("桌面备忘录")
    data = load_data()
    win = MainWindow(data)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
