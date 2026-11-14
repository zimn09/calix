"""Avatar rendering (Qt only).

Every avatar is drawn from primitives with QPainter - no images, no fonts that
need to be embedded, nothing loaded from disk. The widget shows the current
character with the equipped cosmetics (aura, frame, outfit, title).
"""
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen,
                           QRadialGradient)
from PySide6.QtWidgets import QSizePolicy, QWidget

from avatar_data import AVATAR_BY_ID, DEFAULT_AVATAR


def _c(hex_or_color, alpha=255):
    c = QColor(hex_or_color)
    c.setAlpha(alpha)
    return c


class AvatarView(QWidget):
    """A stylised character badge."""

    def __init__(self, avatar_id=DEFAULT_AVATAR, accent="#4dabf7", cosmetics=None, size=150, parent=None):
        super().__init__(parent)
        self.avatar_id = avatar_id if avatar_id in AVATAR_BY_ID else DEFAULT_AVATAR
        self.accent = accent
        self.cosmetics = dict(cosmetics or {})
        self.setFixedSize(size, size)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    # ------------------------------------------------------------------ data
    def set_avatar(self, avatar_id):
        if avatar_id in AVATAR_BY_ID:
            self.avatar_id = avatar_id
        self.update()

    def set_accent(self, color):
        self.accent = color
        self.update()

    def set_cosmetics(self, cosmetics):
        self.cosmetics = dict(cosmetics or {})
        self.update()

    # ----------------------------------------------------------------- paint
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        s = min(w, h)
        a = AVATAR_BY_ID[self.avatar_id]
        accent = self.accent or a["cloth"]
        outfit = self.cosmetics.get("outfit")
        cloth = outfit["color"] if outfit else a["cloth"]

        # ---- background glow
        g = QRadialGradient(QPointF(cx, cy * 0.92), s * 0.5)
        g.setColorAt(0.0, _c(accent, 90))
        g.setColorAt(0.65, _c(accent, 26))
        g.setColorAt(1.0, _c(accent, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(QRectF(cx - s * 0.5, cy - s * 0.5, s, s))

        # ---- aura cosmetic
        aura = self.cosmetics.get("aura")
        if aura:
            col = QColor(aura["color"])
            for i, (rad, alpha, width) in enumerate(((0.47, 220, 3), (0.42, 120, 2), (0.38, 60, 1))):
                p.setPen(QPen(_c(col, alpha), width))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(QRectF(cx - s * rad, cy - s * rad, s * rad * 2, s * rad * 2))
                if i == 0:
                    for k in range(12):
                        ang = k * math.pi / 6
                        x0, y0 = cx + s * rad * math.cos(ang), cy + s * rad * math.sin(ang)
                        x1, y1 = cx + s * (rad + 0.035) * math.cos(ang), cy + s * (rad + 0.035) * math.sin(ang)
                        p.drawLine(QPointF(x0, y0), QPointF(x1, y1))

        # ---- frame cosmetic
        frame = self.cosmetics.get("frame")
        if frame:
            col = QColor(frame["color"])
            p.setPen(QPen(_c(col, 230), 2))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QRectF(cx - s * 0.455, cy - s * 0.455, s * 0.91, s * 0.91))
            p.setPen(QPen(_c(col, 110), 1))
            p.drawEllipse(QRectF(cx - s * 0.425, cy - s * 0.425, s * 0.85, s * 0.85))

        # ---- shoulders / torso
        body_top = cy + s * 0.10
        body = QRectF(cx - s * 0.30, body_top, s * 0.60, s * 0.46)
        lg = QLinearGradient(QPointF(cx, body_top), QPointF(cx, body_top + s * 0.46))
        lg.setColorAt(0.0, _c(cloth, 255))
        lg.setColorAt(1.0, _c(cloth, 130))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(lg))
        p.drawRoundedRect(body, s * 0.16, s * 0.16)
        # collar
        p.setBrush(QColor(0, 0, 0, 70))
        p.drawEllipse(QRectF(cx - s * 0.115, body_top - s * 0.035, s * 0.23, s * 0.10))

        # ---- neck
        p.setBrush(_c(a["skin"]))
        p.drawRoundedRect(QRectF(cx - s * 0.055, cy - s * 0.02, s * 0.11, s * 0.14), s * 0.03, s * 0.03)

        # ---- head
        hr = s * 0.175
        hx, hy = cx, cy - s * 0.115
        p.setBrush(_c(a["skin"]))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(hx - hr, hy - hr, hr * 2, hr * 2))

        shape = a.get("shape", "band")
        hair = a["hair"]

        if shape == "hood":
            p.setBrush(_c(cloth, 235))
            p.drawEllipse(QRectF(hx - hr * 1.30, hy - hr * 1.35, hr * 2.6, hr * 2.6))
            p.setBrush(_c(a["skin"]))
            p.drawEllipse(QRectF(hx - hr * 0.92, hy - hr * 0.98, hr * 1.84, hr * 1.96))
        elif shape == "helm":
            p.setBrush(_c("#9aa4b2"))
            p.drawPie(QRectF(hx - hr * 1.16, hy - hr * 1.22, hr * 2.32, hr * 2.32), 0, 180 * 16)
            p.setBrush(_c("#6b7280"))
            p.drawRoundedRect(QRectF(hx - hr * 0.10, hy - hr * 0.55, hr * 0.20, hr * 1.1), 2, 2)
        elif shape == "topknot":
            p.setBrush(_c(hair))
            p.drawPie(QRectF(hx - hr * 1.05, hy - hr * 1.10, hr * 2.1, hr * 2.1), 0, 180 * 16)
            p.setBrush(_c(hair))
            p.drawEllipse(QRectF(hx - hr * 0.34, hy - hr * 1.62, hr * 0.68, hr * 0.68))
        elif shape == "horns":
            p.setBrush(_c(hair))
            p.drawPie(QRectF(hx - hr * 1.05, hy - hr * 1.08, hr * 2.1, hr * 2.1), 0, 180 * 16)
            p.setBrush(_c("#e9e2c9"))
            for sign in (-1, 1):
                horn = QPainterPath()
                horn.moveTo(hx + sign * hr * 0.80, hy - hr * 0.60)
                horn.lineTo(hx + sign * hr * 1.30, hy - hr * 1.35)
                horn.lineTo(hx + sign * hr * 0.42, hy - hr * 0.95)
                horn.closeSubpath()
                p.setBrush(_c("#e9e2c9"))
                p.drawPath(horn)
        elif shape == "mask":
            p.setBrush(_c(hair))
            p.drawPie(QRectF(hx - hr * 1.04, hy - hr * 1.08, hr * 2.08, hr * 2.08), 0, 180 * 16)
            p.setBrush(_c("#1b2230"))
            p.drawRoundedRect(QRectF(hx - hr * 0.92, hy - hr * 0.10, hr * 1.84, hr * 0.86), hr * 0.25, hr * 0.25)
        elif shape == "wrap":
            p.setBrush(_c(cloth))
            p.drawPie(QRectF(hx - hr * 1.08, hy - hr * 1.18, hr * 2.16, hr * 2.16), 0, 180 * 16)
            p.setBrush(_c(a["skin"]))
            p.drawEllipse(QRectF(hx - hr * 0.88, hy - hr * 0.80, hr * 1.76, hr * 1.70))
        else:  # band
            p.setBrush(_c(hair))
            p.drawPie(QRectF(hx - hr * 1.04, hy - hr * 1.08, hr * 2.08, hr * 2.08), 0, 180 * 16)
            p.setBrush(_c(cloth))
            p.drawRoundedRect(QRectF(hx - hr * 1.02, hy - hr * 0.55, hr * 2.04, hr * 0.30), hr * 0.12, hr * 0.12)

        # ---- eyes
        p.setBrush(_c("#12151c"))
        for sign in (-1, 1):
            p.drawEllipse(QRectF(hx + sign * hr * 0.40 - hr * 0.09, hy - hr * 0.10,
                                 hr * 0.18, hr * 0.22))
        p.end()
