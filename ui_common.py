"""Small reusable widgets and helpers shared by the workout pages."""
import datetime as dt

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QFrame, QLabel, QMessageBox, QToolTip, QVBoxLayout, QWidget


def plain():
    """A transparent container (use inside cards so the card colour shows through)."""
    w = QWidget()
    w.setObjectName("plain")
    return w


def clear_layout(lay):
    while lay.count():
        item = lay.takeAt(0)
        widget, sub = item.widget(), item.layout()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
        elif sub is not None:
            clear_layout(sub)


def fmt_clock(sec):
    m, s = divmod(int(max(0, sec)), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def fmt_duration(sec):
    m = round(int(sec) / 60)
    if m < 60:
        return f"{m} min"
    h, mm = divmod(m, 60)
    return f"{h} h {mm:02d} min"


def pretty_date(d, year=False):
    s = f"{d.strftime('%a %b')} {d.day}"
    return f"{s}, {d.year}" if year else s


def confirm(parent, title, text):
    return QMessageBox.question(parent, title, text) == QMessageBox.Yes


def chip(text, color, filled=True):
    """Small coloured label."""
    lab = QLabel(text)
    lab.setObjectName("chip")
    c = QColor(color)
    bg = f"rgba({c.red()},{c.green()},{c.blue()},{50 if filled else 0})"
    lab.setStyleSheet(f"QLabel#chip {{ color: {color}; background: {bg}; border: 1px solid {color}; }}")
    return lab


class Card(QFrame):
    def __init__(self, title=None, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(16, 14, 16, 14)
        self.lay.setSpacing(8)
        if title:
            t = QLabel(title.upper())
            t.setObjectName("sectionTitle")
            self.lay.addWidget(t)


class StatTile(Card):
    def __init__(self, title, parent=None):
        super().__init__(None, parent)
        self.lay.setSpacing(2)
        self.value = QLabel("0")
        self.value.setObjectName("bigValue")
        cap = QLabel(title.upper())
        cap.setObjectName("sectionTitle")
        self.sub = QLabel("")
        self.sub.setObjectName("muted")
        self.sub.setWordWrap(True)
        for w in (cap, self.value, self.sub):
            self.lay.addWidget(w)

    def set(self, value, sub=""):
        self.value.setText(str(value))
        self.sub.setText(sub)


class BarChart(QWidget):
    """Simple bar chart: data = [(label, value), ...]."""

    def __init__(self, color="#4dabf7", parent=None):
        super().__init__(parent)
        self.color, self.data = QColor(color), []
        self.setMinimumHeight(170)

    def set_data(self, data):
        self.data = list(data)
        self.update()

    def set_color(self, color):
        self.color = QColor(color)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        left, right, top, bottom = 30, 8, 14, 26
        peak = max([v for _, v in self.data] + [1])
        top_val = peak if peak <= 4 else (peak + 1) // 2 * 2
        small = QFont(self.font())
        small.setPointSizeF(8)
        p.setFont(small)
        plot_h = h - top - bottom
        for i in range(5):
            v = top_val * i / 4
            y = top + plot_h - plot_h * i / 4
            p.setPen(QPen(QColor(255, 255, 255, 18), 1))
            p.drawLine(QPointF(left, y), QPointF(w - right, y))
            p.setPen(QColor("#6b7686"))
            p.drawText(QRectF(0, y - 8, left - 5, 16), int(Qt.AlignRight | Qt.AlignVCenter), f"{v:g}")
        if not self.data:
            return
        slot = (w - left - right) / len(self.data)
        bw = slot * 0.58
        for i, (label, v) in enumerate(self.data):
            x = left + slot * i + (slot - bw) / 2
            bh = plot_h * v / top_val
            if v:
                p.setPen(Qt.NoPen)
                p.setBrush(self.color)
                p.drawRoundedRect(QRectF(x, top + plot_h - bh, bw, bh), 3, 3)
                p.setPen(QColor("#e6e9ef"))
                p.drawText(QRectF(x - 6, top + plot_h - bh - 15, bw + 12, 14), int(Qt.AlignCenter), f"{v:g}")
            p.setPen(QColor("#6b7686"))
            p.drawText(QRectF(x - 10, h - bottom + 5, bw + 20, 16), int(Qt.AlignCenter), label)


class Heatmap(QWidget):
    """GitHub-style grid of training days: columns = weeks, rows = weekdays."""
    CELL, GAP, LEFT, TOP = 14, 3, 26, 18

    def __init__(self, weeks=26, parent=None):
        super().__init__(parent)
        self.weeks, self.counts = weeks, {}
        self.today = dt.date.today()
        self.setMouseTracking(True)
        self.setFixedHeight(self.TOP + 7 * (self.CELL + self.GAP) + 4)
        self.setMinimumWidth(self.LEFT + weeks * (self.CELL + self.GAP))

    def set_data(self, counts, today=None):
        self.counts, self.today = counts, today or dt.date.today()
        self.update()

    def _start(self):
        monday = self.today - dt.timedelta(days=self.today.weekday())
        return monday - dt.timedelta(weeks=self.weeks - 1)

    def _color(self, n):
        return QColor("#151b26") if n == 0 else QColor("#1f6f4a") if n == 1 else QColor("#2fa56b") \
            if n == 2 else QColor("#69db7c")

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        small = QFont(self.font())
        small.setPointSizeF(7.5)
        p.setFont(small)
        start, step = self._start(), self.CELL + self.GAP
        p.setPen(QColor("#6b7686"))
        for r, name in ((0, "Mon"), (2, "Wed"), (4, "Fri"), (6, "Sun")):
            p.drawText(QRectF(0, self.TOP + r * step, self.LEFT - 4, self.CELL), int(Qt.AlignRight | Qt.AlignVCenter), name)
        last_month = None
        for wk in range(self.weeks):
            first = start + dt.timedelta(weeks=wk)
            if first.month != last_month and first.day <= 7 + 0:
                p.setPen(QColor("#6b7686"))
                p.drawText(QRectF(self.LEFT + wk * step, 0, 40, self.TOP - 3), int(Qt.AlignLeft | Qt.AlignVCenter),
                           first.strftime("%b"))
            last_month = first.month
            for r in range(7):
                d = first + dt.timedelta(days=r)
                if d > self.today:
                    continue
                p.setPen(Qt.NoPen)
                p.setBrush(self._color(self.counts.get(d, 0)))
                p.drawRoundedRect(QRectF(self.LEFT + wk * step, self.TOP + r * step, self.CELL, self.CELL), 3, 3)

    def mouseMoveEvent(self, e):
        step = self.CELL + self.GAP
        x, y = e.position().x() - self.LEFT, e.position().y() - self.TOP
        if x >= 0 and y >= 0:
            wk, r = int(x // step), int(y // step)
            if wk < self.weeks and r < 7:
                d = self._start() + dt.timedelta(weeks=wk, days=r)
                if d <= self.today:
                    n = self.counts.get(d, 0)
                    QToolTip.showText(e.globalPosition().toPoint(),
                                      f"{pretty_date(d, True)}: {n} workout{'s' if n != 1 else ''}", self)
                    return
        QToolTip.hideText()
