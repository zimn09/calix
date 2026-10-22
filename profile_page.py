"""Profile page: identity, level, achievements, ranks and cosmetic rewards.

The profile is completely local - a name, an avatar and some cosmetics that are
unlocked by reaching levels and achievements. Cosmetics never change any
gameplay value, they only change how the player looks.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QGridLayout, QHBoxLayout,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
                               QPushButton, QScrollArea, QTabWidget, QVBoxLayout, QWidget)

import achievements as AC
from avatar_data import (AVATARS, AVATAR_BY_ID, COSMETICS, COSMETIC_BY_ID, PALETTES,
                         unlock_text)
from avatars import AvatarView
from progress_charts import ProgressPanel
from rank_widgets import rank_html
from ranks import GROUPS, RANKS
from ui_common import Card, StatTile, chip, clear_layout, plain


class AvatarDialog(QDialog):
    """Pick one of the preset characters."""

    def __init__(self, current, accent, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose your fighter")
        self.setMinimumSize(560, 420)
        self.chosen = current
        lay = QVBoxLayout(self)
        grid = QGridLayout()
        grid.setSpacing(8)
        for i, av in enumerate(AVATARS):
            b = QPushButton(f"{av['name']}\n{av['hint']}")
            b.setObjectName("ghost")
            b.setFixedHeight(64)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, a=av["id"]: self._pick(a))
            grid.addWidget(b, i // 2, i % 2)
        wrap = QWidget()
        wrap.setObjectName("plain")
        wrap.setLayout(grid)
        lay.addWidget(wrap)
        box = QDialogButtonBox(QDialogButtonBox.Cancel)
        box.rejected.connect(self.reject)
        lay.addWidget(box)
        self._pick(current)

    def _pick(self, avatar_id):
        self.chosen = avatar_id


class ProfilePage(QWidget):
    """The player profile with the progress dashboard and the cosmetic case."""

    profileChanged = Signal()
    message = Signal(str)

    def __init__(self, store, profiles, ranks, xp, sess, graph=None, parent=None):
        super().__init__(parent)
        self.store, self.profiles = store, profiles
        self.ranks, self.xp, self.sess, self.graph = ranks, xp, sess, graph
        self._build()
        self.refresh()

    # ------------------------------------------------------------------ build
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("sidebar")
        self.tabs.addTab(self._build_overview(), "Overview")
        self.progress = ProgressPanel(self.store, self.sess, self.ranks, self.xp, self.graph)
        self.tabs.addTab(self.progress, "Progress")
        self.tabs.addTab(self._build_cosmetics(), "Cosmetics")
        self.tabs.addTab(self._build_ranks(), "Ranks & achievements")
        root.addWidget(self.tabs)

    # --------------------------------------------------------------- overview
    def _build_overview(self):
        page = QWidget()
        page.setObjectName("plain")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setObjectName("plain")
        body = QWidget()
        body.setObjectName("plain")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        # ---- identity card
        ident = Card("Identity")
        top = QHBoxLayout()
        self.avatar_view = AvatarView(size=180)
        top.addWidget(self.avatar_view)
        col = QVBoxLayout()
        self.name_label = QLabel("")
        self.name_label.setObjectName("pageTitle")
        col.addWidget(self.name_label)
        self.sub_label = QLabel("")
        self.sub_label.setObjectName("muted")
        col.addWidget(self.sub_label)
        name_row = QHBoxLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Your name")
        self.name_edit.setMaxLength(28)
        self.name_edit.returnPressed.connect(self._save_name)
        self.b_save = QPushButton("Save")
        self.b_save.clicked.connect(self._save_name)
        self.b_avatar = QPushButton("Change avatar…")
        self.b_avatar.setObjectName("ghost")
        self.b_avatar.clicked.connect(self._change_avatar)
        name_row.addWidget(self.name_edit, 1)
        name_row.addWidget(self.b_save)
        name_row.addWidget(self.b_avatar)
        cwrap = QWidget()
        cwrap.setObjectName("plain")
        cwrap.setLayout(name_row)
        col.addWidget(cwrap)

        self.palette_row = QHBoxLayout()
        self.palette_row.setSpacing(6)
        self.palette_label = QLabel("Colour")
        self.palette_label.setObjectName("muted")
        self.palette_row.addWidget(self.palette_label)
        self.palette_buttons = {}
        for p in PALETTES:
            b = QPushButton()
            b.setFixedSize(26, 26)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(p["name"])
            b.setStyleSheet(f"background:{p['color']}; border-radius:13px; border:1px solid #ffffff22;")
            b.clicked.connect(lambda _=False, c=p["color"]: self._set_accent(c))
            self.palette_row.addWidget(b)
            self.palette_buttons[p["id"]] = b
        self.palette_row.addStretch(1)
        pwrap = QWidget()
        pwrap.setObjectName("plain")
        pwrap.setLayout(self.palette_row)
        col.addWidget(pwrap)
        cwrap2 = QWidget()
        cwrap2.setObjectName("plain")
        cwrap2.setLayout(col)
        top.addWidget(cwrap2, 1)
        iwrap = QWidget()
        iwrap.setObjectName("plain")
        iwrap.setLayout(top)
        ident.lay.addWidget(iwrap)
        lay.addWidget(ident)

        # ---- stat tiles
        self.tiles = {}
        row1, row2 = QHBoxLayout(), QHBoxLayout()
        for key, title, target in (("level", "Level", row1), ("xp", "Total XP", row1),
                                   ("achievements", "Achievements", row1), ("workouts", "Workouts", row2),
                                   ("prs", "Personal records", row2), ("ranks", "Ranked exercises", row2),
                                   ("skills", "Skills completed", row2)):
            t = StatTile(title)
            self.tiles[key] = t
            target.addWidget(t)
        lay.addLayout(row1)
        lay.addLayout(row2)

        # ---- achievements overview
        self.ach_card = Card("Achievements")
        self.ach_list = QLabel("")
        self.ach_list.setTextFormat(Qt.RichText)
        self.ach_list.setWordWrap(True)
        self.ach_card.lay.addWidget(self.ach_list)
        lay.addWidget(self.ach_card)

        lay.addStretch(1)
        scroll.setWidget(body)
        return scroll

    # -------------------------------------------------------------- cosmetics
    def _build_cosmetics(self):
        page = QWidget()
        page.setObjectName("plain")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setObjectName("plain")
        body = QWidget()
        body.setObjectName("plain")
        self.cos_layout = QVBoxLayout(body)
        self.cos_layout.setContentsMargins(16, 16, 16, 16)
        self.cos_layout.setSpacing(12)
        scroll.setWidget(body)
        self.cos_cards = {}
        for kind, title, hint in (("aura", "Auras", "A glow behind your fighter."),
                                  ("frame", "Frames", "An ornamental border."),
                                  ("outfit", "Outfits", "Recolours the clothing."),
                                  ("title", "Titles", "Shown next to your name.")):
            card = Card(title)
            note = QLabel(hint)
            note.setObjectName("muted")
            card.lay.addWidget(note)
            grid = QGridLayout()
            grid.setSpacing(8)
            card.lay.addLayout(grid)
            self.cos_layout.addWidget(card)
            self.cos_cards[kind] = (card, grid)
        self.cos_layout.addStretch(1)
        return scroll

    # ----------------------------------------------------------------- ranks
    def _build_ranks(self):
        page = QWidget()
        page.setObjectName("plain")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        self.group_row = QHBoxLayout()
        self.group_row.setSpacing(6)
        lay.addLayout(self.group_row)

        self.rank_list = QListWidget()
        lay.addWidget(self.rank_list, 1)
        return page

    # ---------------------------------------------------------------- update
    def refresh(self):
        prof = self.profiles.get()
        if prof is None:
            self.name_label.setText("No profile")
            return
        equipped = {kind: COSMETIC_BY_ID[cid] for kind, cid in self.profiles.equipped().items()
                    if cid in COSMETIC_BY_ID}
        self.avatar_view.set_avatar(prof["avatar"])
        self.avatar_view.set_accent(prof["accent"])
        self.avatar_view.set_cosmetics(equipped)
        title = self.xp.profile()["title"]
        tname = equipped.get("title")
        self.name_label.setText(prof["name"])
        sub = f"Level {self.xp.level().level} {title}"
        if tname:
            sub += f" · {tname['name'].replace('Title: ', '')}"
        self.sub_label.setText(sub)
        self.name_edit.setText(prof["name"])
        self.name_edit.setPlaceholderText(prof["name"])

        p = self.xp.profile()
        hist = self.sess.history(1000)
        results = self.ranks.evaluate_all()
        ranked = [r for r in results.values() if r.rank > 0]
        from database import fetch_all
        prs = fetch_all(self.store.db, """SELECT COUNT(*) AS n FROM (
                                          SELECT exercise_id FROM performances GROUP BY exercise_id)""")
        skills = fetch_all(self.store.db, "SELECT COUNT(*) AS n FROM progress WHERE status='completed'")
        self.tiles["level"].set(p["level"], f"{p['title']} · {p['into']:,}/{p['need']:,} XP")
        self.tiles["xp"].set(f"{p['total']:,}", f"next title: {p['next_title'] or '—'}")
        self.tiles["achievements"].set(f"{p['unlocked']}/{p['count']}", "unlocked")
        self.tiles["workouts"].set(len(hist), "completed")
        self.tiles["prs"].set(prs[0]["n"] if prs else 0, "personal records")
        self.tiles["ranks"].set(len(ranked), f"{len(results)} exercises tracked")
        self.tiles["skills"].set(skills[0]["n"] if skills else 0, "in the skill tree")

        rows = self.xp.achievement_rows()
        unlocked = [r for r in rows if r["unlocked"]]
        unlocked.sort(key=lambda r: r["unlocked"], reverse=True)
        if unlocked:
            lines = []
            for r in unlocked[:12]:
                a = r["a"]
                color = AC.RARITIES[a.rarity][1]
                lines.append(f"<span style='color:{color}'>{a.icon} <b>{a.name}</b></span> "
                             f"<span style='color:#8b95a7'>· {a.description} · {r['unlocked']}</span>")
            self.ach_list.setText("<br>".join(lines))
        else:
            near = self.xp.nearest(3)
            lines = [f"<span style='color:{AC.RARITIES[r['a'].rarity][1]}'>{r['a'].icon} "
                     f"<b>{r['a'].name}</b></span> <span style='color:#8b95a7'>"
                     f"{r['progress']:g}/{r['a'].target:g} {r['a'].unit}</span>" for r in near]
            self.ach_list.setText("Nothing unlocked yet. Closest ones:<br>" + "<br>".join(lines))

        self._refresh_cosmetics()
        self._refresh_ranks(results)
        try:
            self.progress.refresh()
        except Exception:
            pass

    def _refresh_cosmetics(self):
        have = self.profiles.unlocked_ids()
        equipped = self.profiles.equipped()
        for kind, (card, grid) in self.cos_cards.items():
            while grid.count():
                item = grid.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.setParent(None)
                    w.deleteLater()
            for c in COSMETICS:
                if c["kind"] != kind:
                    continue
                box = QWidget()
                box.setObjectName("plain")
                bl = QVBoxLayout(box)
                bl.setContentsMargins(0, 0, 0, 0)
                bl.setSpacing(4)
                unlocked = c["id"] in have
                if kind == "outfit":
                    sw = QWidget()
                    sw.setFixedSize(60, 26)
                    sw.setStyleSheet(f"background:{c['color']}; border-radius:6px;")
                    bl.addWidget(sw)
                elif kind == "title":
                    lab = QLabel(c["name"].replace("Title: ", ""))
                    lab.setStyleSheet(f"color:{c['color']}; font-weight:700;")
                    bl.addWidget(lab)
                elif kind == "aura":
                    sw = QWidget()
                    sw.setFixedSize(60, 26)
                    sw.setStyleSheet(f"background:qradialgradient(cx:50%,cy:50%,radius:50%,"
                                     f"stop:0 {c['color']}, stop:1 transparent);")
                    bl.addWidget(sw)
                else:
                    lab = QLabel("Frame")
                    lab.setStyleSheet(f"color:{c['color']};")
                    bl.addWidget(lab)
                name = QLabel(c["name"])
                name.setObjectName("plain")
                bl.addWidget(name)
                cond = QLabel(c["desc"] if unlocked else unlock_text(c))
                cond.setObjectName("muted")
                cond.setWordWrap(True)
                bl.addWidget(cond)
                if unlocked:
                    btn = QPushButton("Equipped" if equipped.get(kind) == c["id"] else "Equip")
                    btn.setObjectName("ghost")
                    btn.setEnabled(equipped.get(kind) != c["id"])
                    btn.clicked.connect(lambda _=False, cid=c["id"], k=kind: self._equip(k, cid))
                else:
                    btn = QPushButton("Locked")
                    btn.setObjectName("ghost")
                    btn.setEnabled(False)
                bl.addWidget(btn)
                grid.addWidget(box)

    def _equip(self, kind, cosmetic_id):
        self.profiles.equip(kind, cosmetic_id)
        self.refresh()
        self.profileChanged.emit()
        self.message.emit(f"{COSMETIC_BY_ID[cosmetic_id]['name']} equipped")

    # ------------------------------------------------------------ rank lists
    def _refresh_ranks(self, results):
        while self.group_row.count():
            item = self.group_row.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        from collections import defaultdict
        by_group = defaultdict(list)
        for r in results.values():
            by_group[r.track.group].append(r)
        for g, label in GROUPS.items():
            rs = by_group.get(g, [])
            best = max((r.rank for r in rs), default=0)
            c = chip(f"{label}: {RANKS[best][0] if best else '—'}", RANKS[best][1] if best else "#4b5565")
            self.group_row.addWidget(c)
        self.group_row.addStretch(1)

        self.rank_list.clear()
        rows = sorted(results.values(), key=lambda r: (-r.rank, r.track.name))
        for r in rows:
            if r.rank <= 0:
                continue
            it = QListWidgetItem(f"{RANKS[r.rank][0]:<8} {r.track.name}")
            it.setForeground(QColor(RANKS[r.rank][1]))
            it.setToolTip(f"{r.track.name} · {GROUPS[r.track.group]}\n{r.headline}\nnext: {r.goal}")
            it.setData(Qt.UserRole, r.track.exercise_id)
            self.rank_list.addItem(it)

    # ---------------------------------------------------------------- actions
    def _save_name(self):
        name = self.name_edit.text().strip()
        if not name:
            self.message.emit("The name cannot be empty")
            return
        self.profiles.update(name=name)
        self.refresh()
        self.profileChanged.emit()
        self.message.emit("Name saved - your history is untouched")

    def _change_avatar(self):
        prof = self.profiles.get()
        dlg = AvatarDialog(prof["avatar"], prof["accent"], self)
        if dlg.exec() == QDialog.Accepted:
            self.profiles.update(avatar=dlg.chosen)
            self.refresh()
            self.profileChanged.emit()
            self.message.emit("Avatar changed")

    def _set_accent(self, color):
        self.profiles.update(accent=color)
        self.refresh()
        self.profileChanged.emit()
