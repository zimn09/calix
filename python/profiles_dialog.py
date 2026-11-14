"""Profile picker: three local slots, each with its own database.

The dialog only reads local files. Switching closes the dialog and lets the
main window reopen the app with the chosen slot; deleting removes that slot's
SQLite file from this computer.
"""
from PySide6.QtWidgets import (QDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton,
                               QVBoxLayout)

import profile_manager as PM
from avatars import AvatarView
from ui_common import clear_layout


class ProfilesDialog(QDialog):
    """Pick, create or delete one of the three local profile slots."""

    def __init__(self, current_slot=None, parent=None):
        super().__init__(parent)
        self.current_slot = current_slot or PM.get_active_slot()
        self.chosen_slot = None            # set when the app should reopen in another slot
        self.setWindowTitle("Profiles")
        self.setMinimumWidth(600)
        self.setModal(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(12)

        title = QLabel("Profiles")
        title.setObjectName("pageTitle")
        sub = QLabel("Three local slots. Each one keeps its own skill progress, records, workouts and "
                     "history. Everything stays in a file on this computer — no account, no server.")
        sub.setObjectName("muted")
        sub.setWordWrap(True)
        outer.addWidget(title)
        outer.addWidget(sub)

        self.rows = QVBoxLayout()
        self.rows.setSpacing(10)
        outer.addLayout(self.rows)

        self.folder = QLabel("")
        self.folder.setObjectName("muted")
        self.folder.setWordWrap(True)
        outer.addWidget(self.folder)

        bottom = QHBoxLayout()
        hint = QLabel("Switching profiles restarts CALIX.")
        hint.setObjectName("muted")
        bottom.addWidget(hint, 1)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        bottom.addWidget(close)
        outer.addLayout(bottom)
        self._reload()

    # ------------------------------------------------------------------ rows
    def _reload(self):
        clear_layout(self.rows)
        for info in PM.slots():
            self.rows.addWidget(self._row(info))
        self.folder.setText(f"Data folder: {PM.data_root()}")

    def _row(self, info):
        card = QFrame()
        card.setObjectName("card")
        row = QHBoxLayout(card)
        row.setContentsMargins(14, 12, 14, 12)
        row.setSpacing(14)

        avatar = AvatarView(info["avatar"] or "warrior", info["accent"] or "#4dabf7", size=64)
        row.addWidget(avatar)

        col = QVBoxLayout()
        col.setSpacing(2)
        name = QLabel(info["name"] or "Empty slot")
        name.setStyleSheet("font-size: 12pt; font-weight: 700; color: #ffffff;")
        col.addWidget(name)

        state = QLabel(self._state_text(info))
        state.setObjectName("muted")
        state.setWordWrap(True)
        col.addWidget(state)

        if info["name"]:
            if info["slot"] == self.current_slot:
                badge = QLabel("CURRENT PROFILE")
                badge.setObjectName("sectionTitle")
                col.addWidget(badge)
            else:
                badge = QLabel("Ready to train")
                badge.setObjectName("muted")
                col.addWidget(badge)
        row.addLayout(col, 1)

        if info["slot"] == self.current_slot:
            current = QPushButton("Current profile")
            current.setEnabled(False)
            row.addWidget(current)
        elif info["name"]:
            switch = QPushButton("Switch to this profile")
            switch.setObjectName("primary")
            switch.clicked.connect(lambda _=False, s=info["slot"]: self._choose(s))
            row.addWidget(switch)
        else:
            create = QPushButton("Create profile here")
            create.setObjectName("primary")
            create.clicked.connect(lambda _=False, s=info["slot"]: self._choose(s))
            row.addWidget(create)

        if info["exists"]:
            delete = QPushButton("Delete")
            delete.setObjectName("danger")
            delete.clicked.connect(lambda _=False, s=info["slot"], n=info["name"]: self._delete(s, n))
            row.addWidget(delete)
        return card

    @staticmethod
    def _state_text(info):
        if info["name"]:
            xp = f"{info['xp']:,} XP" if info["xp"] else "no XP yet"
            return f"Profile {info['slot']} · Level {info['level']} · {xp}"
        if info["exists"]:
            return f"Profile {info['slot']} · not set up yet — finish the welcome screen"
        return f"Profile {info['slot']} · empty slot"

    # --------------------------------------------------------------- actions
    def _choose(self, slot):
        self.chosen_slot = slot
        self.accept()

    def _delete(self, slot, name):
        who = f"“{name}”" if name else "this unfinished profile"
        if QMessageBox.warning(
                self, "Delete profile",
                f"Delete {who}?<br><br>Its skill progress, records, workouts, schedule and history "
                f"will be permanently removed from this computer. This cannot be undone.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        current = slot == self.current_slot
        PM.delete_slot(slot)
        if current:
            self.chosen_slot = PM.next_slot_after_delete(slot)
            self.accept()
        else:
            self._reload()
