"""Coach page: a chat with the local rule engine, headed by a drawn coach avatar."""
import datetime as dt

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from ui_common import Card, plain

ACCENT = "#4dabf7"
CHIPS = ["hey", "did 3x12 push ups", "and 10 more", "no, 15 reps",
         "sum of reps this week", "what should I train today?"]


def _tint(alpha):
    """The accent as an rgba() string for the stylesheet."""
    c = QColor(ACCENT)
    return f"rgba({c.red()},{c.green()},{c.blue()},{alpha})"


def coach_avatar(size=44, accent=ACCENT):
    """A tiny drawn coach: a man in a disc. No image assets, any DPI."""
    pm = QPixmap(int(size), int(size))
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    w = float(size)
    ink = QColor(accent)

    # disc: soft fill plus a hairline ring
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(ink.red(), ink.green(), ink.blue(), 42))
    p.drawEllipse(QRectF(0.5, 0.5, w - 1.0, w - 1.0))
    ring = QPen(QColor(ink.red(), ink.green(), ink.blue(), 120))
    ring.setWidthF(max(1.0, w * 0.028))
    p.setPen(ring)
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QRectF(w * 0.05, w * 0.05, w * 0.90, w * 0.90))

    # head + shoulders
    p.setPen(Qt.NoPen)
    p.setBrush(ink)
    p.drawEllipse(QRectF(w * 0.355, w * 0.225, w * 0.29, w * 0.29))
    p.drawRoundedRect(QRectF(w * 0.195, w * 0.575, w * 0.61, w * 0.47), w * 0.235, w * 0.235)

    # a collar notch so the shoulders read as a chest, not a blob
    p.setBrush(QColor(0, 0, 0, 80))
    p.drawRoundedRect(QRectF(w * 0.435, w * 0.60, w * 0.13, w * 0.075), w * 0.035, w * 0.035)
    p.end()
    return pm


class Bubble(QFrame):
    """One chat row: avatar (coach only), text bubble, time."""

    def __init__(self, who, text, accent=ACCENT, parent=None):
        super().__init__(parent)
        you = who == "you"
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        body = QLabel(text)
        body.setTextFormat(Qt.PlainText)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        body.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        metrics = body.fontMetrics()
        ideal = max((metrics.horizontalAdvance(line) for line in text.split("\n")), default=120)
        width = int(min(520, max(150, ideal + 36)))
        body.setFixedWidth(width)
        needed = body.heightForWidth(width - 28) + 22
        body.setFixedHeight(max(needed, metrics.height() + 22))
        if you:
            body.setStyleSheet(
                f"QLabel {{ background: {_tint(34)}; border: 1px solid {_tint(105)};"
                " border-radius: 14px; padding: 10px 14px; color: #eaf3ff; }")
        else:
            body.setStyleSheet(
                "QLabel { background: #151d2b; border: 1px solid #223046;"
                " border-radius: 14px; padding: 10px 14px; color: #d9e3f2; }")

        stack = QVBoxLayout()
        stack.setContentsMargins(0, 0, 0, 0)
        stack.setSpacing(3)
        stamp = QLabel(dt.datetime.now().strftime("%H:%M"))
        stamp.setStyleSheet("color: #5d6779; font-size: 8pt;")
        if you:
            stack.addWidget(body, 0, Qt.AlignRight)
            stack.addWidget(stamp, 0, Qt.AlignRight)
            row.addStretch(1)
            row.addLayout(stack, 0)
        else:
            avatar = QLabel()
            avatar.setPixmap(coach_avatar(34, accent))
            avatar.setFixedSize(34, 34)
            avatar.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
            row.addWidget(avatar, 0, Qt.AlignTop)
            stack.addWidget(body, 0, Qt.AlignLeft)
            stack.addWidget(stamp, 0, Qt.AlignLeft)
            row.addLayout(stack, 1)


class CoachPage(QWidget):
    dataChanged = Signal()          # something was written; the shell refreshes the app

    def __init__(self, coach, parent=None):
        super().__init__(parent)
        self.coach = coach
        self.accent = ACCENT
        self._pending = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("pageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        outer.addWidget(scroll)
        body = plain()
        scroll.setWidget(body)
        v = QVBoxLayout(body)
        v.setContentsMargins(18, 16, 18, 18)
        v.setSpacing(12)

        # ---------------------------------------------------------- heading
        top = QHBoxLayout()
        top.setSpacing(12)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel("Coach")
        title.setObjectName("pageTitle")
        sub = QLabel("Understands exercises, numbers and dates right here — no model, no network.")
        sub.setObjectName("muted")
        titles.addWidget(title)
        titles.addWidget(sub)
        top.addLayout(titles, 1)
        badge = QLabel("•  OFFLINE")
        badge.setStyleSheet(
            f"QLabel {{ color: {_tint(235)}; background: {_tint(28)};"
            f" border: 1px solid {_tint(110)}; border-radius: 11px;"
            " padding: 4px 12px; font-size: 8.5pt; font-weight: 800; letter-spacing: 1px; }")
        top.addWidget(badge, 0, Qt.AlignTop)
        v.addLayout(top)

        # ------------------------------------------------------------- hero
        hero = QFrame()
        hero.setObjectName("card")
        h = QHBoxLayout(hero)
        h.setContentsMargins(18, 16, 18, 16)
        h.setSpacing(16)
        face = QLabel()
        face.setPixmap(coach_avatar(64, self.accent))
        face.setFixedSize(64, 64)
        h.addWidget(face, 0, Qt.AlignVCenter)
        info = QVBoxLayout()
        info.setSpacing(4)
        name = QLabel("Your coach")
        name.setStyleSheet("color: #ffffff; font-size: 14pt; font-weight: 800;")
        status = QLabel("•  local engine    ·    no model    ·    works offline")
        status.setStyleSheet("color: #4ad9a9; font-size: 9pt; font-weight: 600;")
        blurb = QLabel("Log what you did, ask about your numbers, or ask what to train next.")
        blurb.setObjectName("muted")
        blurb.setWordWrap(True)
        info.addWidget(name)
        info.addWidget(status)
        info.addWidget(blurb)
        h.addLayout(info, 1)
        v.addWidget(hero)

        # ------------------------------------------------------- conversation
        chat = Card("Conversation")
        chat.lay.setSpacing(10)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("coachFeed")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setMinimumHeight(240)
        self.scroll.setStyleSheet(
            "QScrollArea#coachFeed { background: #0b1119; border: 1px solid #1a2331;"
            " border-radius: 12px; }"
            "QScrollArea#coachFeed > QWidget > QWidget { background: transparent; }")
        self.feed = plain()
        self.feed_lay = QVBoxLayout(self.feed)
        self.feed_lay.setContentsMargins(14, 14, 14, 14)
        self.feed_lay.setSpacing(12)
        self.feed_lay.addStretch(1)
        self.scroll.setWidget(self.feed)
        chat.lay.addWidget(self.scroll, 1)

        # inline save card, hidden until the coach parsed a set
        self.save_card = QFrame()
        self.save_card.setObjectName("coachSave")
        self.save_card.setVisible(False)
        self.save_card.setStyleSheet(
            "QFrame#coachSave { background: rgba(77,171,247,22); border: 1px solid rgba(77,171,247,110);"
            " border-radius: 12px; }"
            "QFrame#coachSave QLabel { background: transparent; }")
        save_lay = QVBoxLayout(self.save_card)
        save_lay.setContentsMargins(14, 12, 14, 12)
        save_lay.setSpacing(8)
        cap = QLabel("SAVE THIS TO YOUR LOG?")
        cap.setStyleSheet("color: #9ecbff; font-size: 8.5pt; font-weight: 800; letter-spacing: 1px;")
        self.save_lines = QLabel("")
        self.save_lines.setWordWrap(True)
        self.save_lines.setStyleSheet("color: #dce7f7;")
        save_lay.addWidget(cap)
        save_lay.addWidget(self.save_lines)
        save_btns = QHBoxLayout()
        save_btns.setSpacing(8)
        save_btn = QPushButton("Save")
        save_btn.setObjectName("primary")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setMinimumHeight(30)
        save_btn.clicked.connect(self._save)
        drop_btn = QPushButton("Discard")
        drop_btn.setObjectName("ghost")
        drop_btn.setCursor(Qt.PointingHandCursor)
        drop_btn.setMinimumHeight(30)
        drop_btn.clicked.connect(self._discard)
        save_btns.addWidget(save_btn)
        save_btns.addWidget(drop_btn)
        save_btns.addStretch(1)
        save_lay.addLayout(save_btns)
        chat.lay.addWidget(self.save_card)

        # starters
        for start in range(0, len(CHIPS), 3):
            row_chips = QHBoxLayout()
            row_chips.setSpacing(8)
            for text in CHIPS[start:start + 3]:
                b = QPushButton(text)
                b.setObjectName("chipButton")
                b.setCursor(Qt.PointingHandCursor)
                b.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
                b.setMaximumHeight(30)
                b.clicked.connect(lambda _=False, t=text: self.ask(t))
                row_chips.addWidget(b)
            row_chips.addStretch(1)
            chat.lay.addLayout(row_chips)

        # composer
        row = QHBoxLayout()
        row.setSpacing(8)
        self.entry = QLineEdit()
        self.entry.setPlaceholderText("Tell the coach what you did, or ask a question…")
        self.entry.returnPressed.connect(self._send)
        self.entry.setClearButtonEnabled(True)
        self.entry.setMinimumHeight(40)
        self.send_btn = QPushButton("Send")
        self.send_btn.setObjectName("primary")
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setMinimumSize(96, 40)
        self.send_btn.clicked.connect(self._send)
        row.addWidget(self.entry, 1)
        row.addWidget(self.send_btn)
        chat.lay.addLayout(row)

        hint = QLabel("Enter to send   ·   everything stays on this machine")
        hint.setStyleSheet("color: #5d6779; font-size: 8.5pt;")
        chat.lay.addWidget(hint)
        v.addWidget(chat, 1)

        self.detail = QLabel("Say hi, log a set, or ask what to train.")
        self.detail.setStyleSheet("color: #66718a; font-size: 8.5pt;")
        v.addWidget(self.detail)

        self._greet()

    # ------------------------------------------------------------------ ui
    def _greet(self):
        self._say("coach", "Hey. I'm right here on this machine — nothing leaves the app. "
                           "Say what you trained, or ask me anything about your numbers.")

    def _bubble(self, who, text):
        self.feed_lay.insertWidget(self.feed_lay.count() - 1, Bubble(who, text, self.accent))
        QTimer.singleShot(0, self._to_bottom)

    def _to_bottom(self):
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _say(self, who, text):
        self._bubble(who, text)

    def ask(self, text):
        """Send text as if the user had typed it."""
        self.entry.setText(text)
        self._send()

    # -------------------------------------------------------------- talking
    def _send(self):
        text = self.entry.text().strip()
        if not text:
            return
        self.entry.clear()
        self._bubble("you", text)
        reply = self.coach.handle(text)
        self._bubble("coach", reply.text)

        bits = [reply.intent, f"{int(reply.confidence * 100)}% sure"]
        if reply.entities:
            bits.append("understood " + ", ".join(reply.entities))
        self.detail.setText("   ·   ".join(bits))

        self._pending = list(reply.actions)
        if self._pending:
            self.save_lines.setText(
                "\n".join(f"• {a.exercise_name}: {a.describe()}" for a in self._pending))
            self.save_card.setVisible(True)
            QTimer.singleShot(0, self._to_bottom)
        else:
            self.save_card.setVisible(False)

    def _save(self):
        notes = [self.coach.apply(a) for a in self._pending]
        for note in notes:
            self._bubble("coach", note)
        self._pending = []
        self.save_card.setVisible(False)
        self.detail.setText("Saved to your log.")
        self.dataChanged.emit()

    def _discard(self):
        self._pending = []
        self.save_card.setVisible(False)
        self._bubble("coach", "Okay, nothing was saved.")
        self.detail.setText("Nothing was saved.")

    # ------------------------------------------------------------ lifecycle
    def refresh(self):
        if self.coach.wrepo is not None:
            from assistant import Vocabulary
            self.coach.vocab = Vocabulary(self.coach.wrepo, self.coach.graph)

    def focus_input(self):
        self.entry.setFocus()
