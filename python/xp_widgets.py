"""XP / level widgets: level badge, level card, XP result formatting and the level-up dialog."""
import math

from PySide6.QtCore import QAbstractAnimation, QPointF, QRectF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget)

import achievements as AC
from ui_common import Card

_ANIMATE = True


def set_animations(on):
    """Follows the Settings > Animations switch (the main window updates it)."""
    global _ANIMATE
    _ANIMATE = bool(on)


class LevelBadge(QWidget):
    """Round level emblem with tick marks; pulses when a level is gained (if animations are on)."""

    def __init__(self, size=72, parent=None):
        super().__init__(parent)
        self.level, self.color, self.pulse, self._anim = 1, "#9aa4b2", 0.0, None
        self.setFixedSize(size, size)

    def set_level(self, level, color):
        self.level, self.color = level, color
        self.update()

    def start_pulse(self):
        if not _ANIMATE:
            return
        anim = QVariantAnimation(self)
        anim.setDuration(900)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setLoopCount(3)
        anim.valueChanged.connect(self._set_pulse)
        anim.start(QAbstractAnimation.DeleteWhenStopped)
        self._anim = anim

    def _set_pulse(self, v):
        self.pulse = float(v)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = min(self.width(), self.height())
        c, col = s / 2, QColor(self.color)
        r = s * 0.37
        if self.pulse > 0:
            ring = QColor(col)
            ring.setAlpha(int(180 * (1 - self.pulse)))
            p.setPen(QPen(ring, max(2.0, s * 0.04)))
            p.setBrush(Qt.NoBrush)
            rr = r * (1.05 + 0.45 * self.pulse)
            p.drawEllipse(QPointF(c, c), rr, rr)
        tick = QColor(col)
        tick.setAlpha(150)
        p.setPen(QPen(tick, max(1.5, s * 0.025)))
        for i in range(12):
            a = math.radians(i * 30)
            p.drawLine(QPointF(c + r * 1.16 * math.cos(a), c + r * 1.16 * math.sin(a)),
                       QPointF(c + r * 1.30 * math.cos(a), c + r * 1.30 * math.sin(a)))
        p.setBrush(QColor("#10141b"))
        p.setPen(QPen(col, max(2.0, s * 0.06)))
        p.drawEllipse(QPointF(c, c), r, r)
        inner = QColor(col)
        inner.setAlpha(70)
        p.setPen(QPen(inner, max(1.0, s * 0.02)))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(c, c), r * 0.78, r * 0.78)
        f = QFont(self.font())
        f.setPixelSize(max(9, int(s * (0.30 if self.level < 100 else 0.22))))
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#ffffff"))
        p.drawText(QRectF(0, 0, s, s), int(Qt.AlignCenter), str(self.level))


def xp_bar(color="#ffd43b"):
    bar = QProgressBar()
    bar.setTextVisible(False)
    bar.setMaximum(1000)
    bar.setStyleSheet(f"QProgressBar::chunk {{ background: {color}; }}")
    return bar


class LevelCard(Card):
    """Level, title, total XP, progress to the next level and achievement count."""

    def __init__(self, xp, parent=None):
        super().__init__(None, parent)
        self.xp = xp
        row = QHBoxLayout()
        row.setSpacing(16)
        self.badge = LevelBadge(84)
        col = QVBoxLayout()
        col.setSpacing(3)
        self.title = QLabel("")
        self.title.setStyleSheet("font-size: 15pt; font-weight: 800;")
        self.total = QLabel("")
        self.bar = xp_bar()
        self.next = QLabel("")
        self.next.setObjectName("muted")
        self.ach = QLabel("")
        self.ach.setObjectName("muted")
        for w in (self.title, self.total, self.bar, self.next, self.ach):
            col.addWidget(w)
        row.addWidget(self.badge)
        row.addLayout(col, 1)
        self.lay.addLayout(row)
        self.refresh()

    def refresh(self):
        p = self.xp.profile()
        self.badge.set_level(p["level"], p["color"])
        self.title.setText(f"Level {p['level']} · <span style='color:{p['color']}'>{p['title']}</span>")
        self.total.setText(f"<b>{p['total']:,}</b> XP total")
        self.bar.setValue(int(p["progress"] * 1000))
        self.bar.setStyleSheet(f"QProgressBar::chunk {{ background: {p['color']}; }}")
        if p["need"]:
            nxt = f" · next title: {p['next_title']} at level {p['next_title_level']}" if p["next_title"] else ""
            self.next.setText(f"{p['into']:,} / {p['need']:,} XP to level {p['level'] + 1}{nxt}")
        else:
            self.next.setText("Maximum level reached")
        self.ach.setText(f"Achievements unlocked: {p['unlocked']} / {p['count']}")


def xp_result_html(res, max_lines=7):
    """XP earned and achievements unlocked by one sync, as rich text. Empty string if nothing happened."""
    if res is None or res.empty:
        return ""
    parts = [f"<p style='font-size:12pt;margin-bottom:2px'><b style='color:#ffd43b'>+{res.gained} XP</b></p>"]
    lines = sorted((a for a in res.awards if a["category"] != "achievement"), key=lambda a: -a["amount"])
    for a in lines[:max_lines]:
        parts.append(f"<span style='color:#69db7c'>+{a['amount']}</span> {a['reason']}<br>")
    if len(lines) > max_lines:
        rest = lines[max_lines:]
        parts.append(f"<span style='color:#8b95a7'>…and {len(rest)} more (+{sum(a['amount'] for a in rest)} XP)</span><br>")
    if res.unlocked:
        parts.append("<p style='margin-bottom:2px'><b style='color:#ffd43b'>Achievements unlocked</b></p>")
        for a in res.unlocked:
            label, color, _ = AC.RARITIES[a.rarity]
            parts.append(f"<span style='color:{color}'>{a.icon} <b>{a.name}</b></span> "
                         f"<span style='color:#8b95a7'>({label}) +{a.xp} XP</span><br>")
    return "".join(parts)


class ProgressionDialog(QDialog):
    """Level-up overview and/or the XP and achievements just earned."""

    def __init__(self, res, parent=None, show_awards=True):
        super().__init__(parent)
        up = res.leveled_up
        self.setWindowTitle("Level up!" if up else "Progress")
        self.setMinimumWidth(440)
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        self.badge = None
        if up:
            a, b = res.level_before, res.level_after
            row = QHBoxLayout()
            self.badge = LevelBadge(110)
            self.badge.set_level(b.level, b.color)
            col = QVBoxLayout()
            head = QLabel("LEVEL UP!")
            head.setStyleSheet("font-size: 20pt; font-weight: 900; color: #ffd43b; letter-spacing: 3px;")
            sub = QLabel(f"Level {a.level} → <b>{b.level}</b> · <span style='color:{b.color}'>{b.title}</span>")
            sub.setTextFormat(Qt.RichText)
            col.addWidget(head)
            col.addWidget(sub)
            if a.title != b.title:
                new = QLabel(f"New title unlocked: <b style='color:{b.color}'>{b.title}</b>")
                new.setTextFormat(Qt.RichText)
                col.addWidget(new)
            bar = xp_bar(b.color)
            bar.setValue(int(b.progress * 1000))
            need = QLabel(f"{b.into:,} / {b.need:,} XP to level {b.level + 1}" if b.need else "Maximum level")
            need.setObjectName("muted")
            col.addWidget(bar)
            col.addWidget(need)
            row.addWidget(self.badge)
            row.addLayout(col, 1)
            lay.addLayout(row)
        if show_awards:
            html = xp_result_html(res)
            if html:
                info = QLabel(html)
                info.setTextFormat(Qt.RichText)
                info.setWordWrap(True)
                lay.addWidget(info)
        ok = QPushButton("Continue")
        ok.setObjectName("primary")
        ok.clicked.connect(self.accept)
        lay.addWidget(ok)
        if self.badge:
            QTimer.singleShot(150, self.badge.start_pulse)


def announce_progress(parent, res, show_awards=True):
    """Show what a sync just credited (XP, achievements, level-up). Does nothing if nothing happened."""
    if res is not None and not res.empty:
        ProgressionDialog(res, parent, show_awards).exec()
