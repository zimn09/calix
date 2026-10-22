"""First-run welcome screen: pick a name and an avatar, then enter the app.

The screen only appears when no local profile exists yet. Everything it
collects is stored in the local SQLite database - no account, no email, no
network access.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QSizePolicy, QVBoxLayout, QWidget)

from avatar_data import AVATARS, PALETTES
from avatars import AvatarView


class AvatarChoice(QFrame):
    """One clickable avatar in the picker grid."""

    clicked = Signal(str)

    def __init__(self, avatar, accent, parent=None):
        super().__init__(parent)
        self.avatar_id = avatar["id"]
        self.setObjectName("plain")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(118, 148)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)
        self.view = AvatarView(avatar["id"], accent, size=96)
        self.view.setAttribute(Qt.WA_TransparentForMouseEvents)
        name = QLabel(avatar["name"])
        name.setAlignment(Qt.AlignCenter)
        name.setObjectName("plain")
        lay.addWidget(self.view, 0, Qt.AlignHCenter)
        lay.addWidget(name)
        self.set_selected(False)

    def set_selected(self, on):
        self.setObjectName("avatarCard")
        color = QColor(self.palette().highlight().color()).name()
        if on:
            self.setStyleSheet(f"QFrame#avatarCard {{ border:2px solid {color}; border-radius:10px; "
                               f"background:{color}22; }}")
        else:
            self.setStyleSheet("QFrame#avatarCard { border:1px solid #1d2430; border-radius:10px; }")


class WelcomePage(QWidget):
    """Shown once, before the main window, when the player has no profile."""

    confirmed = Signal(str, str)       # name, avatar id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("welcome")
        self.avatar_id = AVATARS[0]["id"]
        self.accent = PALETTES[0]["color"]
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(60, 40, 60, 40)
        root.setSpacing(10)

        title = QLabel("CALIX")
        title.setObjectName("pageTitle")
        title.setAlignment(Qt.AlignCenter)
        sub = QLabel("Calisthenics progression · offline RPG")
        sub.setObjectName("muted")
        sub.setAlignment(Qt.AlignCenter)
        root.addWidget(title)
        root.addWidget(sub)

        blurb = QLabel("Welcome. Choose how the world should remember you.<br>"
                       "Everything is stored on this computer - no account, no internet.")
        blurb.setObjectName("muted")
        blurb.setAlignment(Qt.AlignCenter)
        blurb.setWordWrap(True)
        root.addWidget(blurb)
        root.addSpacing(16)

        # ---- avatar grid
        grid_label = QLabel("CHOOSE YOUR FIGHTER")
        grid_label.setObjectName("sectionTitle")
        grid_label.setAlignment(Qt.AlignCenter)
        root.addWidget(grid_label)

        grid = QGridLayout()
        grid.setSpacing(8)
        self.choices = []
        for i, av in enumerate(AVATARS):
            ch = AvatarChoice(av, self.accent)
            ch.clicked.connect(self._pick)
            grid.addWidget(ch, i // 5, i % 5)
            self.choices.append(ch)
        gwrap = QWidget()
        gwrap.setObjectName("plain")
        gwrap.setLayout(grid)
        root.addWidget(gwrap, 1)

        # ---- name
        name_row = QHBoxLayout()
        name_row.addStretch(1)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Your name")
        self.name.setMaxLength(28)
        self.name.setMinimumWidth(260)
        self.name.textChanged.connect(self._check)
        self.start = QPushButton("Enter the arena  →")
        self.start.setObjectName("primary")
        self.start.setMinimumHeight(38)
        self.start.setEnabled(False)
        self.start.clicked.connect(self._confirm)
        name_row.addWidget(self.name)
        name_row.addWidget(self.start)
        name_row.addStretch(1)
        root.addLayout(name_row)

        note = QLabel("You can change your name and avatar later in the Profile page.")
        note.setObjectName("muted")
        note.setAlignment(Qt.AlignCenter)
        root.addWidget(note)

        self._pick(self.avatar_id)

    # ----------------------------------------------------------------- logic
    def _pick(self, avatar_id):
        self.avatar_id = avatar_id
        for ch in self.choices:
            ch.set_selected(ch.avatar_id == avatar_id)

    def _check(self, text):
        self.start.setEnabled(bool(text.strip()))

    def _confirm(self):
        name = self.name.text().strip()
        if not name:
            return
        self.confirmed.emit(name, self.avatar_id)

    def focus_name(self):
        self.name.setFocus()
