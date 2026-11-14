"""Clickable avatar cards shared by the welcome screen and the avatar picker.

The card can be locked behind an achievement. Locked cards are dimmed, show the
achievement that unlocks them and never emit ``clicked`` - so a player cannot
pick an avatar they have not earned yet.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QLabel, QVBoxLayout

from avatars import AvatarView


class AvatarChoice(QFrame):
    """One clickable avatar in the picker grid."""

    clicked = Signal(str)

    def __init__(self, avatar, accent, locked=False, requirement="", parent=None):
        super().__init__(parent)
        self.avatar_id = avatar["id"]
        self.locked = bool(locked)
        self.requirement = requirement
        self.setFixedSize(120, 172)
        self.setCursor(Qt.ForbiddenCursor if self.locked else Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(3)
        self.view = AvatarView(avatar["id"], accent, size=88)
        self.view.setAttribute(Qt.WA_TransparentForMouseEvents)
        if self.locked:
            effect = QGraphicsOpacityEffect(self.view)
            effect.setOpacity(0.35)
            self.view.setGraphicsEffect(effect)
        name = QLabel(avatar["name"])
        name.setAlignment(Qt.AlignCenter)
        name.setObjectName("plain")
        name.setStyleSheet("font-weight: 700;")
        name.setAttribute(Qt.WA_TransparentForMouseEvents)
        status = QLabel(("LOCKED · " + requirement) if self.locked else avatar["hint"])
        status.setAlignment(Qt.AlignCenter)
        status.setObjectName("muted")
        status.setWordWrap(True)
        status.setAttribute(Qt.WA_TransparentForMouseEvents)
        lay.addWidget(self.view, 0, Qt.AlignHCenter)
        lay.addWidget(name)
        lay.addWidget(status)
        if self.locked:
            self.setToolTip(f"Unlock by earning “{requirement}” in any profile")
        self.set_selected(False)

    def set_selected(self, on):
        self.setObjectName("avatarCard")
        color = QColor(self.palette().highlight().color()).name()
        if self.locked:
            self.setStyleSheet(f"QFrame#avatarCard {{ border:1px dashed #46505f; border-radius:10px; "
                               f"background:#ffffff05; }}")
        elif on:
            self.setStyleSheet(f"QFrame#avatarCard {{ border:2px solid {color}; border-radius:10px; "
                               f"background:{color}22; }}")
        else:
            self.setStyleSheet("QFrame#avatarCard { border:1px solid #1d2430; border-radius:10px; }")

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and not self.locked and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self.avatar_id)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if not self.locked and event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.clicked.emit(self.avatar_id)
            event.accept()
            return
        super().keyPressEvent(event)
