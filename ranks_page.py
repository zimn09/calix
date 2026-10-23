"""Ranks page: every exercise's rank on one screen, with filters, details, history and goals."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMessageBox, QProgressBar, QPushButton, QScrollArea,
                               QVBoxLayout, QWidget)

import ranks as R
from rank_widgets import RankBadge, log_performance_dialog, rank_html
from ui_common import Card, chip, clear_layout, confirm, plain
from xp_widgets import announce_progress

GROUP_COLORS = {"pushing": "#ff6b6b", "pulling": "#4dabf7", "core": "#ffd43b", "legs": "#ff922b", "static": "#38d9a9"}


def overview_html(results, n=3):
    """Compact 'strongest + next goals + area to develop' block (used on the Dashboard)."""
    out = []
    top = R.strongest(results, n)
    out.append("<b style='color:#8b95a7'>STRONGEST</b><br>" + ("<br>".join(
        f"{rank_html(r.rank)} &nbsp;{r.track.name} <span style='color:#6b7686'>{r.headline.lower() if r.track.metric != 'line' else ''}</span>"
        for r in top) or "<span style='color:#8b95a7'>Record a performance to get your first rank.</span>"))
    rec = R.recommend(results, n)
    out.append("<br><br><b style='color:#8b95a7'>NEXT GOALS</b><br>" + "<br>".join(
        f"→ <b>{r.track.name}</b>: {r.goal}" for r, _ in rec))
    scores = R.group_scores(results)
    pairs = sorted(scores.items(), key=lambda kv: kv[1])
    if any(v > 0 for v in scores.values()):
        out.append(f"<br><br><b style='color:#8b95a7'>AREA TO DEVELOP</b><br>{R.GROUPS[pairs[0][0]]}")
    return "".join(out)


class RankCard(QFrame):
    clicked = Signal(str)

    def __init__(self, res, selected):
        super().__init__()
        t = res.track
        self.track_id = t.id
        self.setObjectName("rankCard")
        self.setCursor(Qt.PointingHandCursor)
        border = "#e6e9ef" if selected else R.RANKS[res.rank][1] if res.rank else "#1c2431"
        self.setStyleSheet(f"QFrame#rankCard {{ background: #0f141c; border: {2 if selected else 1}px solid {border}; "
                           f"border-radius: 12px; }}")
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(12)
        row.addWidget(RankBadge(54, res.rank), 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(3)
        top = QHBoxLayout()
        name = QLabel(t.name)
        name.setStyleSheet("font-weight: 700; font-size: 10.5pt;")
        top.addWidget(name, 1)
        if t.metric == "line":
            top.addWidget(chip("LINE", "#b197fc"))
        col.addLayout(top)
        sub = QLabel(f"{rank_html(res.rank)} &nbsp;<span style='color:#8b95a7'>{res.headline}</span>")
        sub.setTextFormat(Qt.RichText)
        sub.setWordWrap(True)
        col.addWidget(sub)
        bar = QProgressBar()
        bar.setTextVisible(False)
        bar.setMaximum(1000)
        bar.setValue(int(res.progress * 1000))
        nxt = R.RANKS[min(res.rank + 1, R.MAX_RANK)][1]
        bar.setStyleSheet(f"QProgressBar::chunk {{ background: {nxt}; }}")
        col.addWidget(bar)
        goal = QLabel(res.goal)
        goal.setObjectName("muted")
        goal.setWordWrap(True)
        col.addWidget(goal)
        row.addLayout(col, 1)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit(self.track_id)


class RankPage(QWidget):
    def __init__(self, ranks, wrepo, xp, parent=None):
        super().__init__(parent)
        self.ranks, self.wrepo, self.xp = ranks, wrepo, xp
        self.sel, self.results = None, {}

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        head = QHBoxLayout()
        title = QLabel("Ranks")
        title.setObjectName("pageTitle")
        self.group = QComboBox()
        self.group.addItem("All categories", None)
        for k, label in R.GROUPS.items():
            self.group.addItem(label, k)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search exercises…")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(200)
        self.only_ranked = QCheckBox("Ranked only")
        b_log = QPushButton("Log performance…")
        b_log.setObjectName("primary")
        b_import = QPushButton("Import past workouts")
        b_import.setToolTip("Add the best set of each exercise from your finished workouts as performances")
        for w in (self.group, self.search, self.only_ranked):
            (w.currentIndexChanged if isinstance(w, QComboBox) else
             w.stateChanged if isinstance(w, QCheckBox) else w.textChanged).connect(self._fill_cards)
        b_log.clicked.connect(self._log)
        b_import.clicked.connect(self._import)
        head.addWidget(title, 1)
        for w in (self.group, self.search, self.only_ranked, b_log, b_import):
            head.addWidget(w)
        root.addLayout(head)

        ov = QHBoxLayout()
        ov.setSpacing(12)
        c1, c2, c3 = Card("Strongest exercises"), Card("Recommended goals"), Card("Balance by area")
        self.strong = QLabel("")
        self.goals = QLabel("")
        for lab in (self.strong, self.goals):
            lab.setTextFormat(Qt.RichText)
            lab.setWordWrap(True)
            lab.setAlignment(Qt.AlignTop)
        self.goals.linkActivated.connect(self._link)
        c1.lay.addWidget(self.strong)
        c2.lay.addWidget(self.goals)
        self.g_bars, self.g_labels = {}, {}
        for k, label in R.GROUPS.items():
            row = QHBoxLayout()
            name = QLabel(label)
            name.setFixedWidth(92)
            bar = QProgressBar()
            bar.setTextVisible(False)
            bar.setMaximum(R.MAX_RANK * 100)
            bar.setStyleSheet(f"QProgressBar::chunk {{ background: {GROUP_COLORS[k]}; }}")
            val = QLabel("")
            val.setObjectName("muted")
            val.setFixedWidth(40)
            row.addWidget(name)
            row.addWidget(bar, 1)
            row.addWidget(val)
            c3.lay.addLayout(row)
            self.g_bars[k], self.g_labels[k] = bar, val
        self.balance_note = QLabel("")
        self.balance_note.setObjectName("muted")
        self.balance_note.setWordWrap(True)
        c3.lay.addWidget(self.balance_note)
        for c in (c1, c2, c3):
            ov.addWidget(c, 1)
        root.addLayout(ov)

        body = QHBoxLayout()
        body.setSpacing(12)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("pageScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.cards_box = plain()
        self.grid = QGridLayout(self.cards_box)
        self.grid.setSpacing(10)
        self.grid.setContentsMargins(0, 0, 6, 0)
        self.scroll.setWidget(self.cards_box)
        body.addWidget(self.scroll, 1)
        body.addWidget(self._build_detail())
        root.addLayout(body, 1)
        self.refresh()

    # ----------------------------------------------------------------- detail
    def _build_detail(self):
        card = Card("Details")
        card.setFixedWidth(400)
        top = QHBoxLayout()
        self.d_badge = RankBadge(84, 0)
        info = QVBoxLayout()
        self.d_name = QLabel("Select an exercise")
        self.d_name.setStyleSheet("font-size: 14pt; font-weight: 800;")
        self.d_name.setWordWrap(True)
        self.d_rank = QLabel("")
        self.d_rank.setTextFormat(Qt.RichText)
        self.d_head = QLabel("")
        self.d_head.setObjectName("muted")
        self.d_head.setWordWrap(True)
        for w in (self.d_name, self.d_rank, self.d_head):
            info.addWidget(w)
        top.addWidget(self.d_badge)
        top.addLayout(info, 1)
        card.lay.addLayout(top)
        self.d_bar = QProgressBar()
        self.d_bar.setTextVisible(False)
        self.d_bar.setMaximum(1000)
        self.d_goal = QLabel("")
        self.d_goal.setWordWrap(True)
        self.d_goal.setTextFormat(Qt.RichText)
        self.d_text = QLabel("")
        self.d_text.setTextFormat(Qt.RichText)
        self.d_text.setWordWrap(True)
        self.d_text.setAlignment(Qt.AlignTop)
        self.d_list = QListWidget()
        self.d_list.setMaximumHeight(130)
        row = QHBoxLayout()
        self.b_log = QPushButton("Log performance…")
        self.b_log.setObjectName("primary")
        self.b_del = QPushButton("Delete entry")
        self.b_del.setObjectName("danger")
        self.b_log.clicked.connect(self._log)
        self.b_del.clicked.connect(self._delete_perf)
        row.addWidget(self.b_log)
        row.addWidget(self.b_del)
        for w in (self.d_bar, self.d_goal):
            card.lay.addWidget(w)
        scroll = QScrollArea()
        scroll.setObjectName("pageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = plain()
        il = QVBoxLayout(inner)
        il.setContentsMargins(0, 0, 0, 0)
        il.addWidget(self.d_text)
        il.addStretch(1)
        scroll.setWidget(inner)
        card.lay.addWidget(scroll, 1)
        lab = QLabel("RECENT PERFORMANCES")
        lab.setObjectName("sectionTitle")
        card.lay.addWidget(lab)
        card.lay.addWidget(self.d_list)
        card.lay.addLayout(row)
        return card

    # ---------------------------------------------------------------- refresh
    def refresh(self):
        self.results = self.ranks.evaluate_all()
        res = list(self.results.values())
        top = R.strongest(res, 5)
        self.strong.setText("<br>".join(
            f"{rank_html(r.rank)} &nbsp;<b>{r.track.name}</b><br><span style='color:#6b7686'>{r.headline}</span>"
            for r in top) or "<span style='color:#8b95a7'>Log a performance to earn your first rank.</span>")
        self.goals.setText("<br><br>".join(
            f"<a href='rank:{r.track.id}' style='color:#4dabf7;text-decoration:none'><b>{r.track.name}</b></a><br>"
            f"{r.goal}<br><span style='color:#6b7686'>{why}</span>" for r, why in R.recommend(res, 3)))
        scores = R.group_scores(res)
        for k, v in scores.items():
            self.g_bars[k].setValue(int(v * 100))
            self.g_labels[k].setText(f"{v:.1f}")
        if any(v > 0 for v in scores.values()):
            ordered = sorted(scores.items(), key=lambda kv: kv[1])
            self.balance_note.setText(f"Strongest area: {R.GROUPS[ordered[-1][0]]} · Develop next: {R.GROUPS[ordered[0][0]]}")
        else:
            self.balance_note.setText("Average rank (0-8) per area appears once you log performances.")
        self._fill_cards()
        self._fill_detail()

    def _fill_cards(self, *_):
        clear_layout(self.grid)
        g, q = self.group.currentData(), self.search.text().strip().lower()
        items = [r for r in self.results.values()
                 if (g is None or r.track.group == g) and (not q or q in r.track.name.lower())
                 and (not self.only_ranked.isChecked() or r.rank > 0)]
        order = list(R.GROUPS)
        items.sort(key=lambda r: (order.index(r.track.group), r.track.metric != "line", r.track.difficulty, r.track.name))
        row, col, cur = 0, 0, None
        for r in items:
            if r.track.group != cur:
                cur = r.track.group
                if col:
                    row, col = row + 1, 0
                h = QLabel(R.GROUPS[cur].upper())
                h.setStyleSheet(f"color: {GROUP_COLORS[cur]}; font-weight: 800; letter-spacing: 2px; padding-top: 6px;")
                self.grid.addWidget(h, row, 0, 1, 2)
                row += 1
            card = RankCard(r, r.track.id == self.sel)
            card.clicked.connect(self._select)
            self.grid.addWidget(card, row, col)
            col += 1
            if col == 2:
                row, col = row + 1, 0
        if not items:
            lab = QLabel("No exercises match the filters.")
            lab.setObjectName("muted")
            self.grid.addWidget(lab, 0, 0)
        self.grid.setRowStretch(row + 2, 1)

    def _fill_detail(self):
        res = self.results.get(self.sel)
        self.b_log.setEnabled(res is not None)
        if res is None:
            self.d_name.setText("Select an exercise")
            for w in (self.d_rank, self.d_head, self.d_goal, self.d_text):
                w.setText("")
            self.d_badge.set_rank(0)
            self.d_bar.setValue(0)
            self.d_list.clear()
            self.b_del.setEnabled(False)
            return
        t = res.track
        self.d_badge.set_rank(res.rank)
        self.d_name.setText(t.name)
        self.d_rank.setText(f"{rank_html(res.rank)} &nbsp;<span style='color:#8b95a7'>rank {res.rank}/{R.MAX_RANK}</span>")
        self.d_head.setText(res.headline + (f" · {res.best_date}" if res.best_date and t.metric != "line" else ""))
        self.d_bar.setValue(int(res.progress * 1000))
        nxt = R.RANKS[min(res.rank + 1, R.MAX_RANK)][1]
        self.d_bar.setStyleSheet(f"QProgressBar::chunk {{ background: {nxt}; }}")
        self.d_goal.setText(f"<b>Next goal:</b> {res.goal}")

        html = ["<p style='margin-bottom:2px'><b style='color:#8b95a7'>RANK LADDER</b></p>"]
        for i in range(1, R.MAX_RANK + 1):
            reached = res.rank >= i
            need = (f"{t.thresholds[i - 1]:g} {t.unit}" if t.metric != "line"
                    else f"{t.thresholds[i - 1]:g} of {len(t.steps)} steps")
            html.append(f"<span style='color:{R.RANKS[i][1] if reached else '#4b5565'}'>{'✓' if reached else '○'} "
                        f"<b>{R.RANKS[i][0]}</b></span> <span style='color:#6b7686'>{need}</span><br>")
        if t.metric == "line":
            bests = self._step_bests(t)
            html.append("<p style='margin-bottom:2px'><b style='color:#8b95a7'>PROGRESSION STEPS</b></p>")
            for s in t.steps:
                b = bests.get(s.exercise_id, 0)
                done = b >= s.need
                html.append(f"<span style='color:{'#69db7c' if done else '#8b95a7'}'>{'✓' if done else '○'} {s.name}</span> "
                            f"<span style='color:#6b7686'>need {s.need:g} {s.unit}, best {b:g}</span><br>")
        html.append("<p style='margin-bottom:2px'><b style='color:#8b95a7'>RANK HISTORY</b></p>")
        if res.history:
            html += [f"{rank_html(h.rank)} <span style='color:#6b7686'>{h.date} · "
                     f"{h.value:g} {t.unit if t.metric != 'line' else 'steps'}</span><br>" for h in reversed(res.history)]
        else:
            html.append("<span style='color:#8b95a7'>No rank earned yet.</span>")
        self.d_text.setText("".join(html))

        ids = [t.exercise_id] if t.metric != "line" else [s.exercise_id for s in t.steps]
        perfs = sorted((p for ex in ids for p in self.ranks.performances(ex, 30)), key=lambda p: (p["logged"], p["id"]),
                       reverse=True)[:30]
        self.d_list.clear()
        for p in perfs:
            unit = self.ranks.by_exercise[p["exercise_id"]].unit
            it = QListWidgetItem(f"{p['logged']} · {p['name']} · {p['value']:g} {unit} · {p['source']}")
            it.setData(Qt.UserRole, p["id"])
            self.d_list.addItem(it)
        self.b_del.setEnabled(bool(perfs))

    def _step_bests(self, t):
        out = {}
        for s in t.steps:
            out[s.exercise_id] = self.results[s.exercise_id].best if s.exercise_id in self.results else 0
        return out

    # ---------------------------------------------------------------- actions
    def _select(self, track_id):
        self.sel = track_id
        self._fill_cards()
        self._fill_detail()

    def _link(self, href):
        if href.startswith("rank:"):
            self.select_track(href[5:])

    def select_track(self, track_id):
        self.group.setCurrentIndex(0)
        self.search.clear()
        self._select(track_id)

    def _log(self):
        res = self.results.get(self.sel)
        ex, only = None, None
        if res is not None:
            if res.track.metric == "line":
                only = {s.exercise_id for s in res.track.steps}
            else:
                ex = res.track.exercise_id
        log_performance_dialog(self, self.ranks, ex, only, self.xp)         # repo notifies -> main refreshes pages

    def _delete_perf(self):
        it = self.d_list.currentItem()
        if it and confirm(self, "Delete entry", "Delete this performance? Ranks are recalculated."):
            self.ranks.delete_performance(it.data(Qt.UserRole))

    def _import(self):
        if confirm(self, "Import past workouts", "Add the best completed set of each exercise from your finished "
                                                 "workouts as performances? This only adds missing entries."):
            n = self.ranks.import_history()
            QMessageBox.information(self, "Import", f"Imported {n} performance{'s' if n != 1 else ''}.")
            announce_progress(self, self.xp.sync())
