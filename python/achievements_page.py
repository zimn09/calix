"""Achievements page: gallery with filters, level overview and the XP history."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QProgressBar, QScrollArea, QTableWidget, QTableWidgetItem, QTabWidget,
                               QVBoxLayout, QWidget)

import achievements as AC
from ui_common import chip, clear_layout, plain
from xp_engine import CATEGORY_LABELS
from xp_widgets import LevelCard


def _value(row):
    a = row["a"]
    unit = f" {a.unit}" if a.unit else ""
    shown = a.target if row["unlocked"] else row["progress"]
    return f"{shown:g} / {a.target:g}{unit}"


class AchievementCard(QFrame):
    def __init__(self, row):
        super().__init__()
        a, got = row["a"], row["unlocked"]
        label, color, _ = AC.RARITIES[a.rarity]
        edge = color if got else "#1c2431"
        self.setObjectName("achCard")
        self.setStyleSheet(f"QFrame#achCard {{ background: {'#111826' if got else '#0d1118'}; "
                           f"border: {2 if got else 1}px solid {edge}; border-radius: 12px; }}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(12)
        icon = QLabel(a.icon)
        icon.setFixedSize(48, 48)
        icon.setAlignment(Qt.AlignCenter)
        bg = f"rgba({int(color[1:3], 16)},{int(color[3:5], 16)},{int(color[5:7], 16)},45)" if got else "transparent"
        icon.setStyleSheet(f"background: {bg}; color: {color if got else '#4b5565'}; font-size: 18pt; "
                           f"font-weight: 800; border: 2px solid {color if got else '#2b3341'}; border-radius: 24px;")
        lay.addWidget(icon, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(3)
        top = QHBoxLayout()
        name = QLabel(a.name)
        name.setStyleSheet(f"font-weight: 700; font-size: 10.5pt; color: {color if got else '#aab4c3'};")
        top.addWidget(name, 1)
        top.addWidget(chip(label.upper(), color if got else "#667085", filled=bool(got)))
        col.addLayout(top)
        desc = QLabel(a.description)
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #8b95a7;")
        col.addWidget(desc)
        bar_row = QHBoxLayout()
        bar = QProgressBar()
        bar.setTextVisible(False)
        bar.setMaximum(1000)
        bar.setValue(1000 if got else int(row["pct"] * 1000))
        bar.setStyleSheet(f"QProgressBar::chunk {{ background: {color if got else '#3a4454'}; }}")
        val = QLabel(_value(row))
        val.setObjectName("muted")
        bar_row.addWidget(bar, 1)
        bar_row.addWidget(val)
        col.addLayout(bar_row)
        foot = QLabel(f"✓ Unlocked {got} · +{a.xp} XP" if got else f"Locked · reward +{a.xp} XP")
        foot.setStyleSheet(f"color: {'#69db7c' if got else '#6b7686'}; font-size: 9pt;")
        col.addWidget(foot)
        lay.addLayout(col, 1)


class AchievementsPage(QWidget):
    def __init__(self, xp, parent=None):
        super().__init__(parent)
        self.xp = xp
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        title = QLabel("Achievements")
        title.setObjectName("pageTitle")
        root.addWidget(title)
        self.level_card = LevelCard(xp)
        root.addWidget(self.level_card)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        # ---- gallery
        gallery = QWidget()
        gl = QVBoxLayout(gallery)
        gl.setContentsMargins(0, 10, 0, 0)
        filt = QHBoxLayout()
        self.cat = QComboBox()
        self.cat.addItem("All categories", None)
        for k, v in AC.CATEGORY_LABELS.items():
            self.cat.addItem(v, k)
        self.status = QComboBox()
        for label, key in (("All", None), ("Unlocked", "yes"), ("Locked", "no")):
            self.status.addItem(label, key)
        self.rarity = QComboBox()
        self.rarity.addItem("All rarities", None)
        for k, (label, _, _) in AC.RARITIES.items():
            self.rarity.addItem(label, k)
        self.count = QLabel("")
        self.count.setObjectName("muted")
        for w in (self.cat, self.status, self.rarity):
            w.currentIndexChanged.connect(self._fill_gallery)
            filt.addWidget(w)
        filt.addStretch(1)
        filt.addWidget(self.count)
        gl.addLayout(filt)
        scroll = QScrollArea()
        scroll.setObjectName("pageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self.box = plain()
        self.grid = QGridLayout(self.box)
        self.grid.setSpacing(10)
        self.grid.setContentsMargins(0, 0, 6, 0)
        scroll.setWidget(self.box)
        gl.addWidget(scroll, 1)
        self.tabs.addTab(gallery, "Gallery")

        # ---- XP history
        hist = QWidget()
        hl = QVBoxLayout(hist)
        hl.setContentsMargins(0, 10, 0, 0)
        row = QHBoxLayout()
        self.h_cat = QComboBox()
        self.h_cat.addItem("All sources", None)
        for k, v in CATEGORY_LABELS.items():
            self.h_cat.addItem(v, k)
        self.h_cat.currentIndexChanged.connect(self._fill_history)
        self.h_sum = QLabel("")
        self.h_sum.setObjectName("muted")
        self.h_sum.setWordWrap(True)
        row.addWidget(self.h_cat)
        row.addWidget(self.h_sum, 1)
        hl.addLayout(row)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Date", "XP", "Source", "Reason"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 110)
        self.table.setColumnWidth(1, 70)
        self.table.setColumnWidth(2, 140)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        hl.addWidget(self.table, 1)
        self.h_note = QLabel("")
        self.h_note.setObjectName("muted")
        hl.addWidget(self.h_note)
        self.tabs.addTab(hist, "XP history")
        self.refresh()

    def refresh(self):
        self.level_card.refresh()
        self._fill_gallery()
        self._fill_history()

    def _fill_gallery(self, *_):
        rows = self.xp.achievement_rows()
        done = sum(1 for r in rows if r["unlocked"])
        cat, st, rar = self.cat.currentData(), self.status.currentData(), self.rarity.currentData()
        rows = [r for r in rows if (cat is None or r["a"].category == cat) and (rar is None or r["a"].rarity == rar)
                and (st is None or (st == "yes") == bool(r["unlocked"]))]
        order = list(AC.CATEGORY_LABELS)
        rows.sort(key=lambda r: (order.index(r["a"].category), AC.RARITIES[r["a"].rarity][2], r["a"].target))
        clear_layout(self.grid)
        r_, c_, cur = 0, 0, None
        for row in rows:
            if row["a"].category != cur:
                cur = row["a"].category
                if c_:
                    r_, c_ = r_ + 1, 0
                h = QLabel(AC.CATEGORY_LABELS[cur].upper())
                h.setStyleSheet("color: #8b95a7; font-weight: 800; letter-spacing: 2px; padding-top: 6px;")
                self.grid.addWidget(h, r_, 0, 1, 2)
                r_ += 1
            self.grid.addWidget(AchievementCard(row), r_, c_)
            c_ += 1
            if c_ == 2:
                r_, c_ = r_ + 1, 0
        if not rows:
            lab = QLabel("No achievements match the filters.")
            lab.setObjectName("muted")
            self.grid.addWidget(lab, 0, 0)
        self.grid.setRowStretch(r_ + 2, 1)
        self.count.setText(f"{len(rows)} shown · {done}/{len(self.xp.achievement_rows())} unlocked overall")

    def _fill_history(self, *_):
        cat = self.h_cat.currentData()
        rows = self.xp.history(cat, 500)
        self.table.setRowCount(len(rows))
        for r, e in enumerate(rows):
            for c, text in enumerate((e["earned_on"], f"+{e['amount']}", CATEGORY_LABELS.get(e["category"], e["category"]),
                                      e["reason"])):
                it = QTableWidgetItem(text)
                if c == 1:
                    it.setForeground(QColor("#69db7c"))
                self.table.setItem(r, c, it)
        parts = self.xp.breakdown()
        self.h_sum.setText("Total by source: " + " · ".join(f"{CATEGORY_LABELS.get(k, k)} {v:,}" for k, v in
                                                            sorted(parts.items(), key=lambda kv: -kv[1])) if parts
                           else "No XP earned yet. Finish a workout, set a record or complete a skill.")
        self.h_note.setText(f"Latest {len(rows)} entries. XP is only credited for recorded activity, and each "
                            f"achievement pays once.")
