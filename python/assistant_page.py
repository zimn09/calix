"""Coach page: a chat with the local rule engine, painted as a little coach avatar."""
import datetime as dt

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from ui_common import Card, confirm, plain


CHIPS = ["hey", "did 3x12 push ups", "and 10 more", "no, 15 reps",
         "sum of reps this week", "what should I train today?"]


def coach_avatar(size=44, accent="#4dabf7"):
    """A tiny drawn coach: a man in a disc. No image assets, any DPI."""
    ratio = 1
    pm = QPixmap(int(size * ratio), int(size * ratio))
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    w = size * ratio

    # disc
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(accent).darker(420))
    p.drawEllipse(QRectF(0, 0, w, w))
    p.setBrush(QColor(accent).darker(300))
    p.drawEllipse(QRectF(w * 0.06, w * 0.06, w * 0.88, w * 0.88))

    # head + shoulders
    body = QColor(accent)
    p.setBrush(body)
    p.drawEllipse(QRectF(w * 0.34, w * 0.24, w * 0.32, w * 0.32))
    p.drawRoundedRect(QRectF(w * 0.20, w * 0.58, w * 0.60, w * 0.52), w * 0.30, w * 0.30)

    # a shoulder line to read as a chest, not a blob
    p.setBrush(QColor(accent).darker(240))
    p.drawRoundedRect(QRectF(w * 0.34, w * 0.62, w * 0.32, w * 0.10), w * 0.05, w * 0.05)
    p.end()
    return pm


class Bubble(QFrame):
    """One chat row: avatar (coach only), text bubble, time."""

    def __init__(self, who, text, accent, parent=None):
        super().__init__(parent)
        you = who == "you"
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        body = QLabel(text)
        body.setTextFormat(Qt.PlainText)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        body.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        metrics = body.fontMetrics()
        ideal = max((metrics.horizontalAdvance(line) for line in text.split("\n")), default=120)
        width = int(min(560, max(170, ideal + 34)))
        body.setFixedWidth(width)
        needed = body.heightForWidth(width - 24) + 20        # padding from the stylesheet
        body.setFixedHeight(max(needed, metrics.height() + 20))
        if you:
            body.setStyleSheet(
                "QLabel { background: rgba(77,171,247,40); border: 1px solid rgba(77,171,247,90);"
                " border-radius: 12px; padding: 9px 12px; color: #e6edf7; }")
        else:
            body.setStyleSheet(
                "QLabel { background: #141c28; border: 1px solid #1f2a3a;"
                " border-radius: 12px; padding: 9px 12px; color: #cdd8e6; }")

        stack = QVBoxLayout()
        stack.setContentsMargins(0, 0, 0, 0)
        stack.setSpacing(2)
        stamp = QLabel(dt.datetime.now().strftime("%H:%M"))
        stamp.setObjectName("muted")
        stamp.setStyleSheet("color: #5b6577; font-size: 8pt;")
        if you:
            stack.addWidget(body, 0, Qt.AlignRight)
            stack.addWidget(stamp, 0, Qt.AlignRight)
            row.addStretch(1)
            row.addLayout(stack, 0)
        else:
            avatar = QLabel()
            avatar.setPixmap(coach_avatar(40, accent))
            avatar.setFixedSize(42, 42)
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
        self.accent = "#4dabf7"

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
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(12)

        title = QLabel("Coach")
        title.setObjectName("pageTitle")
        v.addWidget(title)

        # ---- header: the coach himself
        head = Card("")
        head.lay.setSpacing(6)
        who = QHBoxLayout()
        who.setSpacing(12)
        face = QLabel()
        face.setPixmap(coach_avatar(56, self.accent))
        face.setFixedSize(58, 58)
        who.addWidget(face, 0, Qt.AlignTop)
        names = QVBoxLayout()
        names.setSpacing(2)
        name = QLabel("Coach")
        name.setStyleSheet("color: #ffffff; font-size: 13pt; font-weight: 700;")
        status = QLabel("● local engine · no model · works offline")
        status.setStyleSheet("color: #38d9a9; font-size: 9pt;")
        blurb = QLabel("Log what you did, ask about your numbers, or ask what to train next.")
        blurb.setObjectName("muted")
        names.addWidget(name)
        names.addWidget(status)
        names.addWidget(blurb)
        who.addLayout(names, 1)
        head.lay.addLayout(who)
        v.addWidget(head)

        # ---- conversation
        chat = Card("Conversation")
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setMinimumHeight(300)
        self.feed = plain()
        self.feed_lay = QVBoxLayout(self.feed)
        self.feed_lay.setContentsMargins(2, 2, 2, 2)
        self.feed_lay.setSpacing(10)
        self.feed_lay.addStretch(1)
        self.scroll.setWidget(self.feed)
        chat.lay.addWidget(self.scroll, 1)

        chips = QHBoxLayout()
        chips.setSpacing(6)
        for text in CHIPS:
            b = QPushButton(text)
            b.setObjectName("small")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, t=text: self.ask(t))
            chips.addWidget(b)
        chips.addStretch(1)
        chat.lay.addLayout(chips)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.entry = QLineEdit()
        self.entry.setPlaceholderText("Tell the coach what you did, or ask a question…")
        self.entry.returnPressed.connect(self._send)
        self.entry.setClearButtonEnabled(True)
        self.entry.setMinimumHeight(32)
        self.send_btn = QPushButton("Send")
        self.send_btn.setObjectName("primary")
        self.send_btn.setMinimumHeight(32)
        self.send_btn.clicked.connect(self._send)
        row.addWidget(self.entry, 1)
        row.addWidget(self.send_btn)
        chat.lay.addLayout(row)
        v.addWidget(chat, 1)

        self.detail = QLabel("Waiting for the first message.")
        self.detail.setObjectName("muted")
        self.detail.setWordWrap(True)
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

    def _send(self):
        text = self.entry.text().strip()
        if not text:
            return
        self.entry.clear()
        self._bubble("you", text)
        reply = self.coach.handle(text)
        self._bubble("coach", reply.text)
        bits = [f"{reply.intent}", f"{int(reply.confidence * 100)}% sure"]
        if reply.entities:
            bits.append("understood " + ", ".join(reply.entities))
        self.detail.setText("   ·   ".join(bits))

        if reply.actions:
            lines = "\n".join(f"• {a.exercise_name}: {a.describe()}" for a in reply.actions)
            if confirm(self, "Save this to your log?", lines):
                notes = [self.coach.apply(a) for a in reply.actions]
                for note in notes:
                    self._bubble("coach", note)
                self.dataChanged.emit()
            else:
                self._bubble("coach", "Okay, nothing was saved.")

    # ------------------------------------------------------------ lifecycle
    def refresh(self):
        if self.coach.wrepo is not None:
            from assistant import Vocabulary
            self.coach.vocab = Vocabulary(self.coach.wrepo, self.coach.graph)

    def focus_input(self):
        self.entry.setFocus()
